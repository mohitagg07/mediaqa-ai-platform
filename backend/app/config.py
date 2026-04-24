from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path

# ── Resolve .env path relative to THIS file, not the working directory ───────
# This file lives at:  backend/app/config.py
# .env lives at:       backend/.env
# Going up two levels: backend/app/ → backend/
_HERE = Path(__file__).resolve().parent          # → .../backend/app/
_ENV_FILE = _HERE.parent / ".env"                # → .../backend/.env


class Settings(BaseSettings):
    # App
    APP_NAME: str = "MediaQA"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "mediaqa"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    SECRET_KEY: str = "change-me-in-production-super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Groq — llama3-8b-8192 was decommissioned, use llama-3.1-8b-instant
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # HuggingFace Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Whisper (faster-whisper model size)
    WHISPER_MODEL: str = "base"

    # FAISS
    FAISS_INDEX_PATH: str = "./faiss_indexes"

    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 500

    class Config:
        # ✅ FIX: absolute path derived from __file__ — works regardless of
        # which directory uvicorn is started from (backend/, project root, Docker).
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
