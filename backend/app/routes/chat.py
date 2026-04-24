import json
import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.services import mongo_service, rag_service, llm_service, whisper_service
from app.services.rate_limiter import check_rate_limit
from app.utils.jwt_utils import get_current_user_optional

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


async def _get_context_chunks(request: ChatRequest, doc: dict) -> list[str]:
    """
    Retrieve RAG context chunks for the query.

    Recovery order:
      1. FAISS index in memory          (normal hot path)
      2. FAISS index on disk            (server restarted, index still saved)
      3. Rebuild from MongoDB chunks    (disk index also missing — last resort)
      4. Return [] and answer from summary (summary-only fallback)
    """
    search_results = rag_service.semantic_search(
        file_id=request.file_id,
        query=request.question,
        top_k=4,
    )

    # If semantic_search returned empty, try to rebuild from MongoDB chunks
    if not search_results:
        stored_chunks = doc.get("chunks", [])
        if stored_chunks:
            logger.info(
                f"FAISS index missing for {request.file_id} — "
                f"rebuilding from {len(stored_chunks)} MongoDB chunks"
            )
            rebuilt = rag_service.rebuild_index_from_chunks(
                request.file_id, stored_chunks
            )
            if rebuilt:
                search_results = rag_service.semantic_search(
                    file_id=request.file_id,
                    query=request.question,
                    top_k=4,
                )

    # Absolute fallback: use summary or transcript as single context chunk
    if not search_results:
        fallback_text = (
            doc.get("summary")
            or doc.get("transcript")
            or doc.get("text_content")
            or ""
        )
        if fallback_text.strip():
            logger.warning(
                f"Using summary/transcript fallback for {request.file_id}"
            )
            return [fallback_text[:3000]]
        return []

    return [chunk for chunk, _ in search_results]


def _extract_timestamp(doc: dict, context_chunks: list[str]):
    """Try to find the most relevant timestamp from audio/video segments."""
    if doc.get("type") not in ("audio", "video"):
        return None, None
    timestamps = doc.get("timestamps", [])
    if not timestamps or not context_chunks:
        return None, None
    top_chunk = llm_service.find_relevant_timestamp_chunk(
        "", context_chunks   # query not needed — top chunk already ranked
    )
    if not top_chunk:
        return None, None
    matched = whisper_service.find_timestamp_for_text(top_chunk, timestamps)
    if matched:
        return matched["start"], matched["text"]
    return None, None


@router.post("", response_model=ChatResponse)
async def chat(
    http_request: Request,
    request: ChatRequest,
    current_user: str = Depends(get_current_user_optional),
):
    """RAG-powered Q&A over an uploaded file (blocking response)."""
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

    doc = await mongo_service.get_file_document(request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        logger.info(f"RAG query [{request.file_id}]: {request.question[:60]}")
        context_chunks = await _get_context_chunks(request, doc)

        if not context_chunks:
            return ChatResponse(
                answer="I couldn't find relevant information in this document.",
                sources=[],
            )

        answer = llm_service.answer_question(request.question, context_chunks)
        source_previews = [c[:120] + "..." for c in context_chunks]
        timestamp, timestamp_text = _extract_timestamp(doc, context_chunks)

        return ChatResponse(
            answer=answer,
            timestamp=timestamp,
            timestamp_text=timestamp_text,
            sources=source_previews,
        )

    except RuntimeError as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected chat error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/stream")
async def chat_stream(
    http_request: Request,
    request: ChatRequest,
    current_user: str = Depends(get_current_user_optional),
):
    """
    Real-time streaming chat via Server-Sent Events (SSE).

    Stream format:
      data: <token>\\n\\n          — incremental LLM token
      data: [META]<json>\\n\\n    — timestamp + sources after streaming
      data: [DONE]\\n\\n          — stream complete
      data: [ERROR]<msg>\\n\\n   — error occurred
    """
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

    doc = await mongo_service.get_file_document(request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    async def event_generator():
        try:
            # Step 1: get context (with full fallback chain)
            context_chunks = await _get_context_chunks(request, doc)

            if not context_chunks:
                yield "data: I couldn't find relevant information in this document.\n\n"
                yield "data: [DONE]\n\n"
                return

            source_previews = [c[:120] + "..." for c in context_chunks]

            # Step 2: stream LLM tokens
            async for token in llm_service.stream_answer_question(
                request.question, context_chunks
            ):
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"

            # Step 3: send metadata after full answer
            timestamp, timestamp_text = _extract_timestamp(doc, context_chunks)
            meta = json.dumps({
                "timestamp": timestamp,
                "timestamp_text": timestamp_text,
                "sources": source_previews,
            })
            yield f"data: [META]{meta}\n\n"
            yield "data: [DONE]\n\n"

        except RuntimeError as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: [ERROR]{str(e)}\n\n"
        except Exception as e:
            logger.error(f"Unexpected streaming error: {e}")
            yield "data: [ERROR]An unexpected error occurred\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
