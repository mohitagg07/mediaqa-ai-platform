import pytest
import io
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data


@pytest.mark.asyncio
async def test_upload_pdf(client, mock_mongo, mock_pdf, mock_rag, mock_llm):
    """Test PDF upload flow end-to-end."""
    pdf_content = b"%PDF-1.4 fake pdf content for testing"
    files = {"file": ("test_doc.pdf", io.BytesIO(pdf_content), "application/pdf")}

    response = await client.post("/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["type"] == "pdf"
    assert data["filename"] == "test_doc.pdf"
    assert "message" in data

    # Verify pipeline was called
    mock_pdf.assert_called_once()
    mock_rag["chunk"].assert_called_once()
    mock_rag["build"].assert_called_once()
    mock_llm["summary"].assert_called_once()
    mock_mongo["save"].assert_called_once()


@pytest.mark.asyncio
async def test_upload_audio(client, mock_mongo, mock_whisper, mock_rag, mock_llm):
    """Test audio upload and transcription flow."""
    audio_content = b"fake mp3 audio content"
    files = {"file": ("interview.mp3", io.BytesIO(audio_content), "audio/mpeg")}

    response = await client.post("/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "audio"
    mock_whisper.assert_called_once()


@pytest.mark.asyncio
async def test_upload_video(client, mock_mongo, mock_whisper, mock_rag, mock_llm):
    """Test video upload flow."""
    video_content = b"fake mp4 video content"
    files = {"file": ("lecture.mp4", io.BytesIO(video_content), "video/mp4")}

    response = await client.post("/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "video"


@pytest.mark.asyncio
async def test_upload_unsupported_type(client):
    """Test that unsupported file types are rejected."""
    files = {"file": ("malware.exe", io.BytesIO(b"bad content"), "application/octet-stream")}
    response = await client.post("/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_files_empty(client, mock_mongo):
    """Test listing files when none uploaded."""
    mock_mongo["list"].return_value = []
    response = await client.get("/upload/files")
    assert response.status_code == 200
    assert response.json()["files"] == []


@pytest.mark.asyncio
async def test_get_file_info(client, mock_mongo):
    """Test fetching file info by ID."""
    mock_mongo["get"].return_value = {
        "file_id": "abc-123",
        "filename": "test.pdf",
        "type": "pdf",
        "summary": "Test summary",
        "chunks": ["chunk1"],
        "timestamps": [],
    }
    response = await client.get("/upload/files/abc-123")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "abc-123"


@pytest.mark.asyncio
async def test_get_file_not_found(client, mock_mongo):
    """Test 404 when file does not exist."""
    mock_mongo["get"].return_value = None
    response = await client.get("/upload/files/nonexistent-id")
    assert response.status_code == 404
