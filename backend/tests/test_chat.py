import pytest
from unittest.mock import patch


MOCK_FILE_DOC = {
    "file_id": "test-file-123",
    "filename": "lecture.mp4",
    "type": "video",
    "transcript": "This is the transcript of the lecture about machine learning.",
    "text_content": None,
    "chunks": ["chunk about ML", "chunk about neural networks"],
    "timestamps": [
        {"start": 0.0, "end": 5.0, "text": "This is the transcript"},
        {"start": 5.0, "end": 10.0, "text": "of the lecture about machine learning."},
    ],
    "summary": "A lecture on ML topics.",
}

MOCK_PDF_DOC = {
    "file_id": "pdf-file-456",
    "filename": "notes.pdf",
    "type": "pdf",
    "transcript": None,
    "text_content": "Detailed notes about AI systems and RAG pipelines.",
    "chunks": ["AI systems chunk", "RAG pipeline chunk"],
    "timestamps": [],
    "summary": "Notes on AI.",
}


@pytest.mark.asyncio
async def test_chat_video_with_timestamp(client, mock_mongo, mock_rag, mock_llm):
    """Test chat returns answer + timestamp for video files."""
    mock_mongo["get"].return_value = MOCK_FILE_DOC

    response = await client.post("/chat", json={
        "file_id": "test-file-123",
        "question": "What is machine learning?"
    })

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "This is a test answer from the LLM."
    assert "timestamp" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)


@pytest.mark.asyncio
async def test_chat_pdf_no_timestamp(client, mock_mongo, mock_rag, mock_llm):
    """Test chat for PDF returns answer without timestamp."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    response = await client.post("/chat", json={
        "file_id": "pdf-file-456",
        "question": "Explain RAG pipelines"
    })

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["timestamp"] is None


@pytest.mark.asyncio
async def test_chat_file_not_found(client, mock_mongo, mock_rag):
    """Test 404 when chat references non-existent file."""
    mock_mongo["get"].return_value = None

    response = await client.post("/chat", json={
        "file_id": "nonexistent-id",
        "question": "What is this about?"
    })

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_empty_question(client, mock_mongo):
    """Test that empty questions are rejected."""
    mock_mongo["get"].return_value = MOCK_FILE_DOC

    response = await client.post("/chat", json={
        "file_id": "test-file-123",
        "question": "   "
    })

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_chat_no_results(client, mock_mongo, mock_llm):
    """Test graceful handling when no relevant chunks found."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.rag_service.semantic_search", return_value=[]):
        response = await client.post("/chat", json={
            "file_id": "pdf-file-456",
            "question": "What is the weather?"
        })

    assert response.status_code == 200
    data = response.json()
    assert "couldn't find" in data["answer"].lower()


@pytest.mark.asyncio
async def test_chat_rag_error(client, mock_mongo):
    """Test 500 when RAG service fails."""
    mock_mongo["get"].return_value = MOCK_PDF_DOC

    with patch("app.services.rag_service.semantic_search",
               side_effect=RuntimeError("FAISS index not found")):
        response = await client.post("/chat", json={
            "file_id": "pdf-file-456",
            "question": "Test question"
        })

    assert response.status_code == 500
