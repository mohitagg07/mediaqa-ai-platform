import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ─── RAG Service Unit Tests ─────────────────────────────────────────

class TestChunkText:
    def test_basic_chunking(self):
        from app.services.rag_service import chunk_text
        text = "word " * 200  # 200 words
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) > 0

    def test_empty_text_returns_empty_list(self):
        from app.services.rag_service import chunk_text
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        from app.services.rag_service import chunk_text
        text = "Short text."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_overlap_preserves_context(self):
        from app.services.rag_service import chunk_text
        text = "alpha " * 100 + "beta " * 100
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 2


class TestFAISSIndex:
    def test_build_and_search(self):
        """Integration test: build index then search."""
        from app.services.rag_service import build_faiss_index, semantic_search

        chunks = [
            "Machine learning is a subset of artificial intelligence.",
            "Deep learning uses neural networks with many layers.",
            "Natural language processing handles text data.",
            "Computer vision processes images and video.",
        ]
        file_id = "unit-test-file-001"

        with patch("app.services.rag_service.get_embedding_model") as mock_model_fn:
            # Mock the embedding model
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(len(chunks), 384).astype("float32")
            mock_model_fn.return_value = mock_model

            with patch("builtins.open", MagicMock()), \
                 patch("pickle.dump"), \
                 patch("os.makedirs"):
                result = build_faiss_index(file_id, chunks)
                assert result is True

            # Now search
            mock_model.encode.return_value = np.random.rand(1, 384).astype("float32")
            results = semantic_search(file_id, "What is deep learning?", top_k=2)
            assert len(results) <= 2
            for chunk_text, distance in results:
                assert isinstance(chunk_text, str)
                assert isinstance(distance, float)

    def test_search_missing_index_raises(self):
        from app.services.rag_service import semantic_search
        with patch("app.services.rag_service.load_faiss_index", return_value=False):
            with pytest.raises(RuntimeError, match="No FAISS index found"):
                semantic_search("nonexistent-file", "test query")


# ─── PDF Service Unit Tests ────────────────────────────────────────

class TestPDFService:
    def test_extract_text_success(self):
        from app.services.pdf_service import extract_text_from_pdf
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample extracted text from page."
        mock_doc.__len__.return_value = 2
        mock_doc.load_page.return_value = mock_page

        with patch("fitz.open", return_value=mock_doc):
            result = extract_text_from_pdf("/fake/path.pdf")

        assert result is not None
        assert "Sample extracted text" in result
        assert "[Page 1]" in result

    def test_extract_empty_pdf(self):
        from app.services.pdf_service import extract_text_from_pdf
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "   "
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page

        with patch("fitz.open", return_value=mock_doc):
            result = extract_text_from_pdf("/fake/empty.pdf")

        assert result is None

    def test_extract_raises_on_corrupt_file(self):
        from app.services.pdf_service import extract_text_from_pdf
        with patch("fitz.open", side_effect=Exception("Corrupted PDF")):
            with pytest.raises(RuntimeError, match="Failed to extract PDF text"):
                extract_text_from_pdf("/fake/corrupt.pdf")


# ─── Whisper Service Unit Tests ────────────────────────────────────

class TestWhisperService:
    def test_find_timestamp_for_text_match(self):
        from app.services.whisper_service import find_timestamp_for_text
        timestamps = [
            {"start": 0.0, "end": 3.0, "text": "Hello world this is a test"},
            {"start": 3.0, "end": 6.0, "text": "machine learning neural networks"},
            {"start": 6.0, "end": 9.0, "text": "Python programming language"},
        ]
        result = find_timestamp_for_text("machine learning", timestamps)
        assert result is not None
        assert result["start"] == 3.0
        assert "machine" in result["text"].lower()

    def test_find_timestamp_empty_list(self):
        from app.services.whisper_service import find_timestamp_for_text
        result = find_timestamp_for_text("anything", [])
        assert result is None

    def test_transcribe_audio_success(self):
        from app.services.whisper_service import transcribe_audio
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "  Hello world  ",
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Hello world"},
            ]
        }
        with patch("app.services.whisper_service.get_whisper_model", return_value=mock_model):
            result = transcribe_audio("/fake/audio.mp3")

        assert result["transcript"] == "Hello world"
        assert len(result["timestamps"]) == 1
        assert result["timestamps"][0]["start"] == 0.0
        assert result["language"] == "en"


# ─── LLM Service Unit Tests ────────────────────────────────────────

class TestLLMService:
    def test_answer_question_success(self):
        from app.services.llm_service import answer_question
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  The answer is 42.  "
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.llm_service.get_groq_client", return_value=mock_client):
            result = answer_question("What is the answer?", ["context chunk"])

        assert result == "The answer is 42."

    def test_generate_summary_success(self):
        from app.services.llm_service import generate_summary
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Summary of the document."
        mock_client.chat.completions.create.return_value = mock_response

        with patch("app.services.llm_service.get_groq_client", return_value=mock_client):
            result = generate_summary("Long document text " * 100)

        assert "Summary" in result

    def test_answer_question_raises_on_api_error(self):
        from app.services.llm_service import answer_question
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        with patch("app.services.llm_service.get_groq_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="LLM error"):
                answer_question("question", ["context"])


# ─── Auth Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_and_login(client, mock_mongo):
    """Test user registration then login flow."""
    from app.utils.jwt_utils import hash_password

    # Register
    mock_mongo["save"].return_value = True
    response = await client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepass123"
    })
    assert response.status_code == 201

    # Login
    hashed = hash_password("securepass123")
    mock_mongo["get"].return_value = {
        "username": "testuser",
        "hashed_password": hashed
    }
    response = await client.post("/auth/login", json={
        "username": "testuser",
        "password": "securepass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, mock_mongo):
    """Test login fails with wrong password."""
    from app.utils.jwt_utils import hash_password
    mock_mongo["get"].return_value = {
        "username": "testuser",
        "hashed_password": hash_password("correctpassword")
    }
    response = await client.post("/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


# ─── Summary Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_cached_summary(client, mock_mongo):
    """Test that cached summary is returned without calling LLM."""
    mock_mongo["get"].return_value = {
        "file_id": "file-789",
        "summary": "Cached summary text."
    }
    response = await client.get("/summary/file-789")
    assert response.status_code == 200
    assert response.json()["summary"] == "Cached summary text."


@pytest.mark.asyncio
async def test_get_summary_file_not_found(client, mock_mongo):
    mock_mongo["get"].return_value = None
    response = await client.get("/summary/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_summary_on_demand(client, mock_mongo, mock_llm):
    """Test on-demand summary generation when not cached."""
    mock_mongo["get"].return_value = {
        "file_id": "file-999",
        "summary": None,
        "text_content": "Long document content to summarize. " * 50,
        "transcript": None,
    }
    response = await client.get("/summary/file-999")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "This is a test summary of the document."
    mock_llm["summary"].assert_called_once()
