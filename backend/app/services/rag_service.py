"""
rag_service.py — FAISS vector search with disk persistence

KEY FIXES vs original:
  - FAISS indexes are saved to disk (faiss_indexes/<file_id>.faiss +
    faiss_indexes/<file_id>.chunks.pkl) so they survive server restarts.
  - semantic_search() auto-loads from disk when index is not in memory.
  - chunk_size: 500 → 1000 / overlap: 50 → 200 for better coverage.
  - Minimum chunk size filter (skip tiny fragments).
"""

import os
import pickle
import logging
import numpy as np
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer
import faiss
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_embedding_model: Optional[SentenceTransformer] = None
_indexes: dict = {}   # {file_id: (faiss_index, chunks_list)}  — in-memory cache


# ── Helpers: disk paths ──────────────────────────────────────────────────────

def _faiss_path(file_id: str) -> str:
    return os.path.join(settings.FAISS_INDEX_PATH, f"{file_id}.faiss")

def _chunks_path(file_id: str) -> str:
    return os.path.join(settings.FAISS_INDEX_PATH, f"{file_id}.chunks.pkl")


# ── Embedding model ──────────────────────────────────────────────────────────

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _embedding_model


# ── Text chunking ────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> List[str]:
    """
    Split text into overlapping chunks.
    chunk_size: approximate characters per chunk
    overlap: characters carried over to next chunk for continuity
    """
    if not text or not text.strip():
        return []

    words = text.split()
    chunks, chunk_words, char_count = [], [], 0

    for word in words:
        chunk_words.append(word)
        char_count += len(word) + 1

        if char_count >= chunk_size:
            chunk_str = " ".join(chunk_words)
            if len(chunk_str.strip()) >= 50:   # skip tiny fragments
                chunks.append(chunk_str)
            # Carry overlap words into next chunk
            overlap_text = " ".join(chunk_words)[-overlap:]
            chunk_words = overlap_text.split()
            char_count = sum(len(w) + 1 for w in chunk_words)

    if chunk_words:
        last = " ".join(chunk_words)
        if len(last.strip()) >= 50:
            chunks.append(last)

    logger.info(f"Created {len(chunks)} chunks from {len(text)} chars")
    return chunks


# ── FAISS index build + persist ──────────────────────────────────────────────

def build_faiss_index(file_id: str, chunks: List[str]) -> None:
    """
    Build a FAISS flat-IP index for the given chunks,
    cache it in memory AND save it to disk so it survives restarts.
    """
    if not chunks:
        logger.warning(f"No chunks to index for {file_id}")
        return

    model = get_embedding_model()
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    embeddings = embeddings.astype(np.float32)
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Memory cache
    _indexes[file_id] = (index, chunks)

    # ── Disk persistence ────────────────────────────────────────────────────
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    try:
        faiss.write_index(index, _faiss_path(file_id))
        with open(_chunks_path(file_id), "wb") as f:
            pickle.dump(chunks, f)
        logger.info(
            f"FAISS index saved to disk for {file_id}: "
            f"{len(chunks)} vectors, dim={dim}"
        )
    except Exception as e:
        logger.warning(f"Could not save FAISS index to disk for {file_id}: {e}")

    logger.info(
        f"FAISS index built for {file_id}: {len(chunks)} vectors, dim={dim}"
    )


def _load_index_from_disk(file_id: str) -> bool:
    """
    Try to load a previously saved FAISS index from disk into memory.
    Returns True if successful.
    """
    fp, cp = _faiss_path(file_id), _chunks_path(file_id)
    if not (os.path.isfile(fp) and os.path.isfile(cp)):
        return False
    try:
        index = faiss.read_index(fp)
        with open(cp, "rb") as f:
            chunks = pickle.load(f)
        _indexes[file_id] = (index, chunks)
        logger.info(f"FAISS index loaded from disk for {file_id}: {len(chunks)} chunks")
        return True
    except Exception as e:
        logger.warning(f"Failed to load FAISS index from disk for {file_id}: {e}")
        return False


def rebuild_index_from_chunks(file_id: str, chunks: List[str]) -> bool:
    """
    Rebuild FAISS index from raw text chunks (e.g. loaded from MongoDB).
    Called as a last-resort fallback in semantic_search.
    """
    if not chunks:
        return False
    logger.info(f"Rebuilding FAISS index from {len(chunks)} chunks for {file_id}")
    build_faiss_index(file_id, chunks)
    return True


# ── Semantic search (with auto-restore) ─────────────────────────────────────

def semantic_search(
    file_id: str,
    query: str,
    top_k: int = 4,
) -> List[Tuple[str, float]]:
    """
    Retrieve the top_k most relevant chunks for the query.
    Auto-restores the FAISS index from disk if not in memory
    (handles server restarts gracefully).
    Returns list of (chunk_text, score) tuples.
    """
    # 1. Try memory cache
    if file_id not in _indexes:
        # 2. Try disk
        if not _load_index_from_disk(file_id):
            logger.warning(
                f"No FAISS index for {file_id} — "
                "file was uploaded in a previous session. "
                "Caller should pass chunks for rebuild."
            )
            return []

    index, chunks = _indexes[file_id]
    model = get_embedding_model()

    query_emb = model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(query_emb)

    k = min(top_k, len(chunks))
    scores, indices = index.search(query_emb, k)

    results = [
        (chunks[idx], float(score))
        for score, idx in zip(scores[0], indices[0])
        if idx >= 0
    ]
    logger.info(
        f"Semantic search returned {len(results)} results for file {file_id}"
    )
    return results
