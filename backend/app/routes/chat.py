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


async def _resolve_rag(request: ChatRequest, doc: dict) -> tuple[str, list, list]:
    """Shared RAG resolution used by both /chat and /chat/stream."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    search_results = rag_service.semantic_search(
        file_id=request.file_id,
        query=request.question,
        top_k=4,
    )
    context_chunks = [chunk for chunk, _ in search_results]
    source_previews = [chunk[:120] + "..." for chunk in context_chunks]

    # Timestamp matching
    timestamp = None
    timestamp_text = None
    if doc.get("type") in ("audio", "video"):
        timestamps = doc.get("timestamps", [])
        if timestamps and context_chunks:
            top_chunk = llm_service.find_relevant_timestamp_chunk(request.question, context_chunks)
            if top_chunk:
                matched = whisper_service.find_timestamp_for_text(top_chunk, timestamps)
                if matched:
                    timestamp = matched["start"]
                    timestamp_text = matched["text"]

    return context_chunks, source_previews, timestamp, timestamp_text


@router.post("", response_model=ChatResponse)
async def chat(
    http_request: Request,
    request: ChatRequest,
    current_user: str = Depends(get_current_user_optional),
):
    """
    RAG-powered Q&A over an uploaded file (blocking response).

    Pipeline: FAISS semantic search → Groq LLM → timestamp extraction.
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

    doc = await mongo_service.get_file_document(request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        logger.info(f"RAG query [{request.file_id}]: {request.question[:60]}")
        search_results = rag_service.semantic_search(
            file_id=request.file_id, query=request.question, top_k=4
        )

        if not search_results:
            return ChatResponse(
                answer="I couldn't find relevant information in this document.",
                sources=[],
            )

        context_chunks = [chunk for chunk, _ in search_results]
        source_previews = [chunk[:120] + "..." for chunk in context_chunks]
        answer = llm_service.answer_question(request.question, context_chunks)

        timestamp = None
        timestamp_text = None
        if doc.get("type") in ("audio", "video"):
            timestamps = doc.get("timestamps", [])
            if timestamps:
                top_chunk = llm_service.find_relevant_timestamp_chunk(
                    request.question, context_chunks
                )
                if top_chunk:
                    matched = whisper_service.find_timestamp_for_text(top_chunk, timestamps)
                    if matched:
                        timestamp = matched["start"]
                        timestamp_text = matched["text"]

        response = ChatResponse(
            answer=answer,
            timestamp=timestamp,
            timestamp_text=timestamp_text,
            sources=source_previews,
        )
        return response

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

    Frontend usage (EventSource / fetch with ReadableStream):
      const resp = await fetch('/chat/stream', { method: 'POST', body: JSON.stringify({...}) });
      const reader = resp.body.getReader();
      // read chunks and render tokens progressively
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

    doc = await mongo_service.get_file_document(request.file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    async def event_generator():
        try:
            # Step 1: semantic search (fast, not streamed)
            search_results = rag_service.semantic_search(
                file_id=request.file_id, query=request.question, top_k=4
            )

            if not search_results:
                yield "data: I couldn't find relevant information in this document.\n\n"
                yield "data: [DONE]\n\n"
                return

            context_chunks = [chunk for chunk, _ in search_results]
            source_previews = [chunk[:120] + "..." for chunk in context_chunks]

            # Step 2: stream LLM tokens
            async for token in llm_service.stream_answer_question(
                request.question, context_chunks
            ):
                # Escape newlines so SSE frames stay single-line
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"

            # Step 3: send metadata (timestamp + sources) after full answer
            timestamp = None
            timestamp_text = None
            if doc.get("type") in ("audio", "video"):
                timestamps = doc.get("timestamps", [])
                if timestamps:
                    top_chunk = llm_service.find_relevant_timestamp_chunk(
                        request.question, context_chunks
                    )
                    if top_chunk:
                        matched = whisper_service.find_timestamp_for_text(top_chunk, timestamps)
                        if matched:
                            timestamp = matched["start"]
                            timestamp_text = matched["text"]

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
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
