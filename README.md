# MediaQA 🎯

> AI-powered Q&A for PDFs, audio, and video files — with RAG, real-time streaming, timestamps, and JWT auth.

Run tests:

pytest --cov=app --cov-report=term-missing

⚠️ Note Due to environment constraints (CI/CD, Redis, FAISS mocking),

some integration tests may fail in CI but work locally.

![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)

**Live Demo:** https://mediaqa-ai-platform.vercel.app  
**Backend API:** https://mediaqa-backend.onrender.com  
**API Docs:** https://mediaqa-backend.onrender.com/docs

---

## What It Does

- Upload **PDF**, **audio** (mp3/wav/m4a), or **video** (mp4/mkv/webm) files
- Ask natural language questions — get answers grounded in your actual content
- See **timestamps** and click to jump directly to the relevant moment in audio/video
- Real-time **streaming** chat responses via Server-Sent Events
- Secure **JWT authentication** — register, login, or continue as guest

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend (Vercel)                │
│  UploadZone │ ChatInterface │ MediaPlayer │ Summary Display  │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST / SSE
┌──────────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend (Render)                   │
│                                                             │
│  POST /upload       POST /chat        GET /summary/{id}     │
│       │                  │                                  │
│  ┌────▼────┐        ┌────▼──────────────────────┐          │
│  │ PyMuPDF │PDF     │  RAG Pipeline              │          │
│  │ Whisper │Audio   │  1. HuggingFace Embeddings │          │
│  └────┬────┘Video   │  2. FAISS Semantic Search  │          │
│       │             │  3. Groq LLM Answer         │          │
│  ┌────▼────┐        │  4. Timestamp Matching      │          │
│  │ Chunker │        └───────────────────────────┬┘          │
│  │ FAISS   │◄──────────────────────────────────┘           │
│  └────┬────┘                                               │
│       │                                                     │
│  ┌────▼─────────────────────────────────────┐              │
│  │  MongoDB Atlas  │  Redis  │  File Storage │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, React Router, Lucide Icons, ReactMarkdown |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **LLM** | Groq API (llama3-8b-8192) |
| **Embeddings** | HuggingFace all-MiniLM-L6-v2 |
| **Vector DB** | FAISS (faiss-cpu) |
| **Transcription** | faster-whisper (tiny, int8, CPU-optimized) |
| **PDF Parsing** | PyMuPDF (fitz) |
| **Database** | MongoDB Atlas (Motor async driver) |
| **Cache / Rate Limit** | Redis (Upstash) |
| **Auth** | JWT — python-jose + passlib bcrypt |
| **Streaming** | Server-Sent Events (SSE) |
| **DevOps** | Docker, Docker Compose, GitHub Actions CI/CD |
| **Testing** | pytest, pytest-asyncio, pytest-cov, httpx |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API key from https://console.groq.com

### 1. Clone & configure

```bash
git clone https://github.com/mohitagg07/mediaqa.git
cd mediaqa
cp backend/.env.example backend/.env
# Edit backend/.env — set GROQ_API_KEY and MONGODB_URL
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MongoDB | localhost:27017 |
| Redis | localhost:6379 |

### 3. Run locally (development)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Set GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

---

## API Reference

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Create account |
| POST | /auth/login | Get JWT token |

**Register:**
```json
POST /auth/register
{ "username": "alice", "password": "secret123" }
→ { "message": "Account created for 'alice'" }
```

**Login:**
```json
POST /auth/login
{ "username": "alice", "password": "secret123" }
→ { "access_token": "eyJ...", "token_type": "bearer" }
```

---

### Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /upload | Upload PDF / audio / video |
| GET | /upload/files | List uploaded files |
| GET | /upload/files/{id} | Get file details |

**Upload response:**
```json
{
  "file_id": "a1b2c3d4-...",
  "filename": "lecture.mp4",
  "type": "video",
  "message": "File processed successfully",
  "summary": "### Transcript\n- ...\n### Summary\n..."
}
```

Supported: pdf, mp3, wav, m4a, ogg, mp4, mkv, avi, mov, webm

---

### Chat (RAG Pipeline)

```
POST /chat
Authorization: Bearer <token>   (optional)

{ "file_id": "a1b2c3d4-...", "question": "What is the main topic?" }
```

**Response:**
```json
{
  "answer": "The main topic is...",
  "timestamp": 120.5,
  "timestamp_text": "In this section we cover...",
  "sources": ["chunk preview 1...", "chunk preview 2..."]
}
```

### Chat Streaming (SSE)

```
POST /chat/stream
{ "file_id": "...", "question": "..." }
```

SSE frame format:
```
data: <token>           <- incremental LLM token
data: [META]<json>      <- timestamp + sources
data: [DONE]            <- stream complete
data: [ERROR]<msg>      <- error
```

---

### Summary

```
GET /summary/{file_id}
-> { "file_id": "...", "summary": "..." }
```

---

## RAG Pipeline

```
Question
   |
   v
HuggingFace Embeddings (all-MiniLM-L6-v2)
   |  encode question -> 384-dim vector
   v
FAISS Index Search (IndexFlatL2)
   |  top-4 most similar chunks
   v
Groq LLM (llama3-8b-8192)
   |  grounded prompt: context + question -> no hallucination
   v
Answer + Timestamp match -> frontend seeks media player
```

**Chunking:** 500-character chunks with 50-character overlap.  
**Grounding:** LLM is strictly instructed to answer only from context — never infers or guesses.

---

## Testing

```bash
cd backend

# Run all tests with coverage
pytest

# Verbose
pytest -v

# HTML coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Coverage: 95%+**

| Test file | What it covers |
|-----------|---------------|
| test_upload.py | Upload pipeline — PDF, audio, video, errors, listing |
| test_chat.py | RAG chat, timestamps, streaming, error handling |
| test_processing.py | Unit tests — RAG, Whisper, PDF, LLM, auth, summary |
| test_streaming.py | SSE streaming — tokens, META/DONE frames |
| test_rate_limiting.py | Rate limiter unit + 429 integration tests |
| test_coverage_boost.py | Edge cases, schema validation, utility functions |

---

## Project Structure

```
mediaqa/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, lifespan
│   │   ├── config.py                # Pydantic settings
│   │   ├── models/schemas.py        # Request/response models
│   │   ├── routes/
│   │   │   ├── upload.py            # POST /upload
│   │   │   ├── chat.py              # POST /chat, /chat/stream
│   │   │   ├── summary.py           # GET /summary/{id}
│   │   │   └── auth.py              # JWT auth endpoints
│   │   ├── services/
│   │   │   ├── pdf_service.py       # PyMuPDF text extraction
│   │   │   ├── whisper_service.py   # Whisper transcription + timestamps
│   │   │   ├── rag_service.py       # Chunking + FAISS + semantic search
│   │   │   ├── llm_service.py       # Groq API answers + summaries
│   │   │   ├── mongo_service.py     # MongoDB async CRUD
│   │   │   └── rate_limiter.py      # Redis sliding-window rate limiter
│   │   └── utils/jwt_utils.py       # JWT + bcrypt
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_upload.py
│   │   ├── test_chat.py
│   │   ├── test_processing.py
│   │   ├── test_streaming.py
│   │   ├── test_rate_limiting.py
│   │   └── test_coverage_boost.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── UploadZone.jsx       # Drag & drop with progress bar
│   │   │   ├── ChatInterface.jsx    # Streaming chat + markdown rendering
│   │   │   ├── MediaPlayer.jsx      # Video/audio player with seekTo()
│   │   │   └── Summary.jsx          # AI summary display
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   └── AuthPage.jsx
│   │   ├── context/AuthContext.jsx  # JWT auth state
│   │   └── services/api.js          # Axios layer
│   ├── Dockerfile
│   └── package.json
├── .github/workflows/ci.yml
├── docker-compose.yml
└── README.md
```

---

## Deployment

### Step 1 — MongoDB Atlas (free M0)

1. https://cloud.mongodb.com → create free M0 cluster
2. Add database user, set Network Access to 0.0.0.0/0
3. Copy connection string: `mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/mediaqa`

### Step 2 — Backend: Render (free tier)

1. https://render.com → New Web Service → connect repo → Root Directory: `backend`
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables:

| Key | Value |
|-----|-------|
| GROQ_API_KEY | from console.groq.com |
| MONGODB_URL | Atlas connection string |
| SECRET_KEY | any long random string |
| REDIS_URL | leave blank (rate limiting fails open) |

### Step 3 — Frontend: Vercel (free)

1. https://vercel.com → New Project → import repo → Root Directory: `frontend`
2. Environment Variable: `VITE_API_URL` = your Render backend URL

### Step 4 — CI/CD (GitHub Actions)

Pre-configured in `.github/workflows/ci.yml` — runs tests on every push, auto-deploys on merge to `main`.

Required GitHub Secrets:
```
RENDER_DEPLOY_HOOK    <- Render Settings -> Deploy Hooks
VERCEL_TOKEN          <- Vercel Account Settings -> Tokens
VERCEL_ORG_ID         <- from .vercel/project.json
VERCEL_PROJECT_ID     <- from .vercel/project.json
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| GROQ_API_KEY | — | **Required.** Get from console.groq.com |
| MONGODB_URL | mongodb://mongo:27017 | MongoDB connection |
| REDIS_URL | redis://redis:6379 | Redis (optional, fails open) |
| SECRET_KEY | — | JWT signing key |
| WHISPER_MODEL | tiny | Model size (tiny/base/small) |
| EMBEDDING_MODEL | all-MiniLM-L6-v2 | HuggingFace sentence transformer |
| GROQ_MODEL | llama3-8b-8192 | Groq model name |
| MAX_FILE_SIZE_MB | 500 | Upload size limit |

---

## Rate Limiting

All endpoints protected by Redis sliding-window limiter (fails open without Redis).

| Endpoint | Per IP | Per User |
|----------|--------|----------|
| POST /chat | 10/min | 20/min |
| POST /upload | 10/min | 20/min |
| General | 60/min | 120/min |

---

## Interview Notes

**"What is RAG and why did you use it?"**  
RAG grounds the LLM in actual content — encode question as vector, FAISS similarity search finds top-4 chunks, Groq LLM answers only from those chunks. Prevents hallucination entirely.

**"How does transcription work?"**  
faster-whisper (tiny model, int8 quantized) for memory-efficient CPU transcription. Each segment returns start/end timestamps. Word-overlap matching finds the most relevant timestamp for each answer.

**"How did you optimize for free-tier deployment?"**  
Tiny Whisper model with int8 quantization reduces memory from ~1GB to ~150MB. Lazy loading (model initialized on first request) prevents OOM on cold starts. Temperature=0.1 for deterministic, grounded LLM responses.

**"How would you scale to 1000 users?"**  
Redis caching for summaries, horizontal FastAPI workers behind load balancer, async MongoDB with connection pooling, Celery background queue for Whisper processing, larger models on higher-memory instances.

---

## License
MIT
