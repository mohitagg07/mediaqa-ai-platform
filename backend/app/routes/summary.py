import logging
from fastapi import APIRouter, HTTPException
from app.models.schemas import SummaryResponse
from app.services import mongo_service, llm_service

router = APIRouter(prefix="/summary", tags=["summary"])
logger = logging.getLogger(__name__)


@router.get("/{file_id}", response_model=SummaryResponse)
async def get_summary(file_id: str):
    """
    Return existing summary or generate one on-demand.
    """
    doc = await mongo_service.get_file_document(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    # Return cached summary if it exists
    if doc.get("summary"):
        return SummaryResponse(file_id=file_id, summary=doc["summary"])

    # Generate summary from available text
    full_text = doc.get("text_content") or doc.get("transcript") or ""
    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text content available for summarization"
        )

    try:
        summary = llm_service.generate_summary(full_text)
        # Cache it
        await mongo_service.update_file_document(file_id, {"summary": summary})
        return SummaryResponse(file_id=file_id, summary=summary)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
