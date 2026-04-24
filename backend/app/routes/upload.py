import os
import uuid
import aiofiles
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.models.schemas import UploadResponse, FileType
from app.services import mongo_service, pdf_service, whisper_service, rag_service, llm_service
from app.services.rate_limiter import check_rate_limit
from app.utils.jwt_utils import get_current_user_optional

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {
    "pdf": FileType.PDF,
    "mp3": FileType.AUDIO,
    "wav": FileType.AUDIO,
    "m4a": FileType.AUDIO,
    "ogg": FileType.AUDIO,
    "mp4": FileType.VIDEO,
    "mkv": FileType.VIDEO,
    "avi": FileType.VIDEO,
    "mov": FileType.VIDEO,
    "webm": FileType.VIDEO,
}


def get_file_type(filename: str) -> FileType:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Allowed: {list(ALLOWED_EXTENSIONS.keys())}"
        )
    return ALLOWED_EXTENSIONS[ext]


@router.post("", response_model=UploadResponse)
async def upload_file(
    http_request: Request,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_optional),
):
    """
    Upload a PDF, audio, or video file.
    Extracts text/transcript, builds RAG index, generates summary.
    """
    # Rate limiting
    client_ip = http_request.client.host if http_request.client else "unknown"
    limited, rl_headers = await check_rate_limit(
        identifier=client_ip, endpoint_type="heavy", user_id=current_user
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down.",
            headers=rl_headers,
        )

    file_type = get_file_type(file.filename)
    file_id = str(uuid.uuid4())

    # Save file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1].lower()
    save_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}.{ext}")

    try:
        async with aiofiles.open(save_path, "wb") as f:
            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
                )
            await f.write(content)

        # Extract content
        text_content = None
        transcript = None
        timestamps = []
        chunks = []

        if file_type == FileType.PDF:
            logger.info(f"Extracting text from PDF: {file_id}")
            text_content = pdf_service.extract_text_from_pdf(save_path)
            chunks = rag_service.chunk_text(text_content or "")

        elif file_type in (FileType.AUDIO, FileType.VIDEO):
            logger.info(f"Transcribing {file_type}: {file_id}")
            result = whisper_service.transcribe_audio(save_path)
            transcript = result["transcript"]
            timestamps = result["timestamps"]
            chunks = rag_service.chunk_text(transcript or "")

        # Build FAISS index
        full_text = text_content or transcript or ""
        if chunks:
            rag_service.build_faiss_index(file_id, chunks)

        # Generate summary
        summary = None
        if full_text.strip():
            try:
                summary = llm_service.generate_summary(full_text)
            except Exception as e:
                logger.warning(f"Summary generation failed: {e}")

        # Save to MongoDB
        doc = {
            "file_id": file_id,
            "filename": file.filename,
            "type": file_type.value,
            "file_path": save_path,
            "transcript": transcript,
            "text_content": text_content,
            "chunks": chunks,
            "timestamps": timestamps,
            "summary": summary,
            "user_id": current_user,
        }
        await mongo_service.save_file_document(doc)

        logger.info(f"File uploaded successfully: {file_id} ({file_type})")
        return UploadResponse(
            file_id=file_id,
            filename=file.filename,
            type=file_type.value,
            message="File processed successfully",
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # Clean up file on error
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )


@router.get("/files")
async def list_files(current_user: str = Depends(get_current_user_optional)):
    """List uploaded files (filtered by user if authenticated)."""
    files = await mongo_service.list_file_documents(user_id=current_user)
    return {"files": files}


@router.get("/files/{file_id}")
async def get_file_info(file_id: str):
    """Get details for a specific uploaded file."""
    doc = await mongo_service.get_file_document(file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    doc.pop("_id", None)
    return doc
