import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override settings for testing
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "mediaqa_test")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """Async test client for FastAPI app."""
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def mock_mongo():
    """Mock MongoDB service calls."""
    with patch("app.services.mongo_service.save_file_document", new_callable=AsyncMock) as mock_save, \
         patch("app.services.mongo_service.get_file_document", new_callable=AsyncMock) as mock_get, \
         patch("app.services.mongo_service.list_file_documents", new_callable=AsyncMock) as mock_list, \
         patch("app.services.mongo_service.update_file_document", new_callable=AsyncMock) as mock_update:
        mock_save.return_value = "test-object-id"
        mock_list.return_value = []
        mock_update.return_value = True
        yield {
            "save": mock_save,
            "get": mock_get,
            "list": mock_list,
            "update": mock_update,
        }


@pytest.fixture
def mock_rag():
    """Mock RAG service."""
    with patch("app.services.rag_service.build_faiss_index") as mock_build, \
         patch("app.services.rag_service.semantic_search") as mock_search, \
         patch("app.services.rag_service.chunk_text") as mock_chunk:
        mock_build.return_value = True
        mock_chunk.return_value = ["chunk1", "chunk2", "chunk3"]
        mock_search.return_value = [
            ("This is relevant context about the question.", 0.15),
            ("Additional context from the document.", 0.25),
        ]
        yield {"build": mock_build, "search": mock_search, "chunk": mock_chunk}


@pytest.fixture
def mock_llm():
    """Mock LLM service."""
    with patch("app.services.llm_service.answer_question") as mock_answer, \
         patch("app.services.llm_service.generate_summary") as mock_summary:
        mock_answer.return_value = "This is a test answer from the LLM."
        mock_summary.return_value = "This is a test summary of the document."
        yield {"answer": mock_answer, "summary": mock_summary}


@pytest.fixture
def mock_pdf():
    """Mock PDF service."""
    with patch("app.services.pdf_service.extract_text_from_pdf") as mock_extract:
        mock_extract.return_value = "Sample PDF text content for testing purposes. " * 20
        yield mock_extract


@pytest.fixture
def mock_whisper():
    """Mock Whisper service."""
    with patch("app.services.whisper_service.transcribe_audio") as mock_transcribe:
        mock_transcribe.return_value = {
            "transcript": "This is a test transcript of the audio file.",
            "timestamps": [
                {"start": 0.0, "end": 3.5, "text": "This is a test"},
                {"start": 3.5, "end": 7.0, "text": "transcript of the audio file."},
            ],
            "language": "en",
        }
        yield mock_transcribe
