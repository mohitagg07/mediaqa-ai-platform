"""
rag_service.py — improved chunking for better retrieval accuracy

KEY FIXES vs original:
  - chunk_size: 500 → 1000  (avoids splitting mid-sentence for structured docs)
  - overlap:    50  → 200   (more context carry-over between chunks)
  - Minimum chunk size filter (skip tiny fragments)
  - Better logging for debugging retrieval issues
"""

import logging
import numpy as np
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer
import faiss
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embedding_model: Optional[SentenceTransformer] = None
_indexes: dict = {}   # {file_id: (faiss_index, chunks_list)}


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _embedding_model


def chunk_text(
    text: str,
    chunk_size: int = 1000,   # ← was 500, now 1000 for better coverage
    overlap: int = 200,        # ← was 50, now 200 for more context
) -> List[str]:
    """
    Split text into overlapping chunks.
    chunk_size: approximate characters per chunk
    overlap: characters carried over to next chunk for continuity
    """
    if not text or not text.strip():
        return []

    words = text.split()
    chunks = []
    chunk_words: List[str] = []
    char_count = 0

    for word in words:
        chunk_words.append(word)
        char_count += len(word) + 1

        if char_count >= chunk_size:
            chunk_str = " ".join(chunk_words)
            # Skip tiny fragments (< 50 chars)
            if len(chunk_str.strip()) >= 50:
                chunks.append(chunk_str)
            # Carry overlap words into next chunk
            overlap_text = " ".join(chunk_words)[-overlap:]
            chunk_words = overlap_text.split()
            char_count = sum(len(w) + 1 for w in chunk_words)

    # Last remaining words
    if chunk_words:
        last = " ".join(chunk_words)
        if len(last.strip()) >= 50:
            chunks.append(last)

    logger.info(f"Created {len(chunks)} chunks from {len(text)} chars")
    return chunks


def build_faiss_index(file_id: str, chunks: List[str]) -> None:
    """Build and cache a FAISS flat-IP index for the given chunks."""
    if not chunks:
        logger.warning(f"No chunks to index for {file_id}")
        return

    model = get_embedding_model()
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    embeddings = embeddings.astype(np.float32)

    # Normalize for cosine similarity via inner product
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    _indexes[file_id] = (index, chunks)
    logger.info(
        f"FAISS index built for {file_id}: {len(chunks)} vectors, dim={dim}"
    )


def semantic_search(
    file_id: str,
    query: str,
    top_k: int = 4,
) -> List[Tuple[str, float]]:
    """
    Retrieve the top_k most relevant chunks for the query.
    Returns list of (chunk_text, score) tuples.
    """
    if file_id not in _indexes:
        logger.warning(f"No FAISS index found for {file_id} — index may have been lost on server restart")
        return []

    index, chunks = _indexes[file_id]
    model = get_embedding_model()

    query_emb = model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(query_emb)

    k = min(top_k, len(chunks))
    scores, indices = index.search(query_emb, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0:
            results.append((chunks[idx], float(score)))

    logger.info(f"Semantic search returned {len(results)} results for file {file_id}")
    return results
