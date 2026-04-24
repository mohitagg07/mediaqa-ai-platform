import os
import logging
from pathlib import Path

# ── Load .env BEFORE anything else ─────────────────────────────────────────
# python-dotenv must populate os.environ BEFORE pydantic-settings reads it,
# because get_settings() is decorated with @lru_cache — the very first call
# freezes the result forever. If .env isn't loaded yet, it falls back to the
# hardcoded default "mongodb://localhost:27017".
#
# We try three candidate paths so this works whether you run uvicorn from:
#   • backend/           → python -m uvicorn app.main:app --reload
#   • project root       → uvicorn backend.app.main:app
#   • inside Docker      → WORKDIR /app, CMD uvicorn app.main:app
from dotenv import load_dotenv as _load_dotenv

_env_candidates = [
    Path(__file__).resolve().parent.parent / ".env",  # backend/.env  ← canonical
    Path(".env"),                                       # cwd/.env      ← fallback
    Path("backend/.env"),                              # project-root run
]
for _p in _env_candidates:
    if _p.exists():
        _load_dotenv(dotenv_path=str(_p), override=True)
        break
# ────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routes import upload, chat, summary, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── Startup confirmation — proves .env loaded correctly ─────────────────────
_mongo_preview = settings.MONGODB_URL[:45] + "..." if len(settings.MONGODB_URL) > 45 else settings.MONGODB_URL
logger.info(f"[CONFIG] MONGODB_URL = {_mongo_preview}")
logger.info(f"[CONFIG] MONGODB_DB  = {settings.MONGODB_DB}")
# ────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    yield
    logger.info("Shutting down...")
    from app.services.mongo_service import close_connection
    from app.services.rate_limiter import close_redis
    await close_connection()
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered media Q&A system with RAG, Whisper, and Groq",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(summary.router)

# ── Static file serving (audio/video playback in frontend) ───────────────────
# This mounts the uploads folder at /static so the media player can stream files.
# URL pattern: http://localhost:8000/static/{file_id}.{ext}
#
# IMPORTANT: This must come AFTER all routers so it doesn't shadow API routes.
_upload_dir = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(_upload_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_upload_dir), name="static")


# ── Health & root ────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "static_files": "/static/<file_id>.<ext>",
    }
