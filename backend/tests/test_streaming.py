"""
test_streaming.py
Tests for the real-time SSE streaming chat endpoint: POST /chat/stream
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


MOCK_VIDEO_DOC = {
    "file_id": "stream-test-001",
    "filename": "lecture.mp4",
    "type": "video",
    "transcript": "This lecture is about machine learning and neural networks.",
    "text_content": None,
    "chunks": ["chunk about ML", "chunk about neural networks"],
    "timestamps": [
        {"start": 0.0, "end": 5.0, "text": "This lecture is about machine learning"},
        {"start": 5.0, "end": 10.0, "text": "and neural networks."},
    ],
    "summary": "A lecture on ML.",
}

MOCK_PDF_DOC = {
    "file_id": "stream-pdf-002",
    "filename": "notes.pdf",
    "type": "pdf",
    "transcript": None,
    "text_content": "Detailed notes about AI and RAG pipelines.",
    "chunks": ["AI chunk", "RAG chunk"],
    "timestamps": [],
    "summary": "Notes on AI.",
}


async def _fake_stream(*args, **kwargs):
    """Async generator that yields fake LLM tokens."""
    tokens = ["The ", "main ", "topic ", "is ", "machine ", "learning."]
    for token in tokens:
        yield token


# ─── Basic streaming tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_returns_sse_content_type(client, mock_mongo, mock_rag):
    """Streaming endpoint must return text/event-stream content type."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.llm_service.stream_answer_question", side_effect=_fake_stream), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "What is AI?"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_stream_yields_tokens(client, mock_mongo, mock_rag):
    """Each LLM token should appear as a 'data:' SSE line."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.llm_service.stream_answer_question", side_effect=_fake_stream), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "Explain RAG"},
        )

    body = response.text
    lines = [l for l in body.split("\n") if l.startswith("data:")]

    # Should have token lines + [META] line + [DONE] line
    assert any("[DONE]" in l for l in lines), "Missing [DONE] sentinel"
    assert any("[META]" in l for l in lines), "Missing [META] metadata frame"
    # At least some token lines
    token_lines = [l for l in lines if "[DONE]" not in l and "[META]" not in l and "[ERROR]" not in l]
    assert len(token_lines) > 0


@pytest.mark.asyncio
async def test_stream_meta_frame_for_video(client, mock_mongo, mock_rag):
    """[META] frame should contain timestamp for video files."""
    mock_mongo["get"].return_value = MOCK_VIDEO_DOC

    with patch("app.services.llm_service.stream_answer_question", side_effect=_fake_stream), \
         patch("app.services.llm_service.find_relevant_timestamp_chunk", return_value="machine learning chunk"), \
         patch("app.services.whisper_service.find_timestamp_for_text",
               return_value={"start": 0.0, "end": 5.0, "text": "This lecture is about machine learning"}), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-test-001", "question": "What is machine learning?"},
        )

    body = response.text
    meta_lines = [l for l in body.split("\n") if "[META]" in l]
    assert len(meta_lines) == 1

    meta_json = meta_lines[0].replace("data: [META]", "").strip()
    meta = json.loads(meta_json)
    assert "timestamp" in meta
    assert "sources" in meta
    assert isinstance(meta["sources"], list)


@pytest.mark.asyncio
async def test_stream_meta_no_timestamp_for_pdf(client, mock_mongo, mock_rag):
    """PDF files should have null timestamp in [META] frame."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.llm_service.stream_answer_question", side_effect=_fake_stream), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "Explain RAG"},
        )

    body = response.text
    meta_lines = [l for l in body.split("\n") if "[META]" in l]
    assert len(meta_lines) == 1
    meta = json.loads(meta_lines[0].replace("data: [META]", "").strip())
    assert meta["timestamp"] is None


# ─── Error handling ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_file_not_found(client, mock_mongo):
    """Returns 404 before streaming starts when file doesn't exist."""
    mock_mongo["get"].return_value = None

    with patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "nonexistent", "question": "Anything?"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_empty_question_rejected(client, mock_mongo):
    """Empty question is rejected with 400 before streaming starts."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "   "},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_stream_no_results_sends_fallback(client, mock_mongo):
    """When FAISS returns no results, stream sends a fallback message."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.rag_service.semantic_search", return_value=[]), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "Unknown topic"},
        )

    assert response.status_code == 200
    body = response.text
    assert "couldn't find" in body.lower()
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_stream_llm_error_sends_error_frame(client, mock_mongo, mock_rag):
    """LLM errors during streaming are surfaced as [ERROR] SSE frames."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    async def failing_stream(*args, **kwargs):
        raise RuntimeError("Groq API timeout")
        yield  # make it a generator

    with patch("app.services.llm_service.stream_answer_question", side_effect=failing_stream), \
         patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "Test"},
        )

    assert response.status_code == 200
    assert "[ERROR]" in response.text


# ─── Rate limiting on /chat/stream ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_rate_limited_returns_429(client, mock_mongo):
    """Rate-limited requests to /chat/stream return HTTP 429."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.rate_limiter.check_rate_limit",
               return_value=(True, {"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "0"})):
        response = await client.post(
            "/chat/stream",
            json={"file_id": "stream-pdf-002", "question": "Test"},
        )

    assert response.status_code == 429
