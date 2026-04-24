# MediaQA 🎯

> AI-powered Q&A for PDFs, audio, and video files — with RAG, timestamps, and Groq LLM.

[![CI/CD](https://github.com/yourusername/mediaqa/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/mediaqa/actions)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](./backend/htmlcov)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│   UploadZone │ ChatInterface │ MediaPlayer │ Summary Display    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / REST
┌──────────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  POST /upload       POST /chat        GET /summary/{id}         │
│       │                  │                                      │
│  ┌────▼────┐        ┌────▼────────────────────────┐            │
│  │ PyMuPDF │PDF     │  RAG Pipeline               │            │
│  │ Whisper │Audio   │  1. Semantic Search (FAISS)  │            │
│  └────┬────┘Video   │  2. HuggingFace Embeddings   │            │
│       │              │  3. Groq LLM Answer          │            │
│  ┌────▼────┐        │  4. Timestamp Match          │            │
│  │ Chunker │        └────────────────────────────┬─┘            │
│  │ FAISS   │◄───────────────────────────────────┘             │
│  │ Indexer │                                                    │
│  └────┬────┘                                                    │
│       │                                                         │
│  ┌────▼──────────────────────────────────────────┐             │
│  │  MongoDB  │  Redis Cache  │  File Storage      │             │
│  └───────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, React Router, Lucide Icons |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **LLM** | Groq API (`llama3-8b-8192`) |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` |
| **Vector DB** | FAISS (faiss-cpu) |
| **Transcription** | OpenAI Whisper |
| **PDF Parsing** | PyMuPDF (fitz) |
| **Database** | MongoDB (Motor async driver) |
| **Cache** | Redis |
| **Auth** | JWT (python-jose + passlib bcrypt) |
| **DevOps** | Docker, Docker Compose, GitHub Actions |
| **Testing** | pytest, pytest-asyncio, pytest-cov, httpx |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API key → https://console.groq.com

### 1. Clone & configure

```bash
git clone https://github.com/yourusername/mediaqa.git
cd mediaqa

# Copy and edit env file
cp backend/.env.example backend/.env
# Set GROQ_API_KEY in backend/.env
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
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get JWT token |

**Register:**
```json
POST /auth/register
{ "username": "alice", "email": "alice@example.com", "password": "secret123" }
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
| `POST` | `/upload` | Upload PDF / audio / video |
| `GET` | `/upload/files` | List uploaded files |
| `GET` | `/upload/files/{id}` | Get file details |

**Upload response:**
```json
{
  "file_id": "a1b2c3d4-...",
  "filename": "lecture.mp4",
  "type": "video",
  "message": "File processed successfully",
  "summary": "This video covers..."
}
```

---

### Chat (RAG Pipeline)

```
POST /chat
Authorization: Bearer <token>

{
  "file_id": "a1b2c3d4-...",
  "question": "What is the main topic?"
}
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

The `timestamp` field (seconds) lets the frontend seek the media player to the exact relevant moment.

---

### Summary

```
GET /summary/{file_id}

→ { "file_id": "...", "summary": "AI-generated summary..." }
```

---

## RAG Pipeline Details

```
Question
   │
   ▼
HuggingFace Embeddings (all-MiniLM-L6-v2)
   │  encode question → 384-dim vector
   ▼
FAISS Index Search (IndexFlatL2)
   │  top-4 most similar chunks
   ▼
Groq LLM (llama3-8b-8192)
   │  prompt = context chunks + question
   ▼
Answer + Timestamp
```

**Chunking strategy:** 500-character chunks with 50-character overlap for context continuity.

---

## Testing

```bash
cd backend

# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_upload.py -v

# Coverage report (HTML)
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Test coverage:** 90%+ across all modules
- `tests/test_upload.py` — upload pipeline (PDF, audio, video, error cases)
- `tests/test_chat.py` — RAG chat, timestamp extraction
- `tests/test_processing.py` — unit tests for RAG, Whisper, PDF, LLM, auth

---

## Project Structure

```
mediaqa/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # Pydantic settings
│   │   ├── models/schemas.py    # Request/response models
│   │   ├── routes/
│   │   │   ├── upload.py        # POST /upload
│   │   │   ├── chat.py          # POST /chat (RAG)
│   │   │   ├── summary.py       # GET /summary
│   │   │   └── auth.py          # JWT auth
│   │   ├── services/
│   │   │   ├── pdf_service.py   # PyMuPDF text extraction
│   │   │   ├── whisper_service.py # Whisper transcription + timestamps
│   │   │   ├── rag_service.py   # Chunking + FAISS indexing + search
│   │   │   ├── llm_service.py   # Groq API (answers + summaries)
│   │   │   └── mongo_service.py # MongoDB CRUD
│   │   └── utils/jwt_utils.py   # JWT encode/decode/hash
│   ├── tests/
│   │   ├── conftest.py          # Fixtures and mocks
│   │   ├── test_upload.py
│   │   ├── test_chat.py
│   │   └── test_processing.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── UploadZone.jsx   # Drag & drop upload with progress
│   │   │   ├── ChatInterface.jsx # Chat UI with streaming-style UX
│   │   │   ├── MediaPlayer.jsx  # Video/audio player with seekTo()
│   │   │   └── Summary.jsx      # AI summary display
│   │   ├── pages/
│   │   │   ├── Home.jsx         # Landing page
│   │   │   ├── Dashboard.jsx    # Main workspace
│   │   │   └── AuthPage.jsx     # Login / register
│   │   ├── context/AuthContext.jsx
│   │   └── services/api.js      # Axios API layer
│   ├── Dockerfile
│   └── package.json
├── .github/workflows/ci.yml     # GitHub Actions CI/CD
├── docker-compose.yml
└── README.md
```

---

## Deployment

> Docker is not required for deployment. The app runs free on Render (backend) + Vercel (frontend) + MongoDB Atlas (database).

---

### Step 1 — Database: MongoDB Atlas (free tier)
1. Sign up at https://cloud.mongodb.com → create a **free M0 cluster**
2. Add a database user (username + password)
3. Under **Network Access** → allow `0.0.0.0/0` (all IPs, needed for Render)
4. Click **Connect → Drivers** → copy the connection string, e.g.:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/mediaqa
   ```
5. Save this as `MONGODB_URL` — you'll need it in Step 2

---

### Step 2 — Backend: Render (free tier)
1. Sign up at https://render.com → **New → Web Service**
2. Connect your GitHub repo, set **Root Directory** to `backend`
3. Fill in:
   | Field | Value |
   |-------|-------|
   | Environment | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
4. Under **Environment Variables**, add:
   | Key | Value |
   |-----|-------|
   | `GROQ_API_KEY` | your key from console.groq.com |
   | `MONGODB_URL` | Atlas connection string from Step 1 |
   | `SECRET_KEY` | any long random string |
   | `REDIS_URL` | leave blank (rate limiting fails open safely) |
5. Click **Deploy** → copy the URL, e.g. `https://mediaqa-api.onrender.com`
6. For CI/CD: **Settings → Deploy Hooks** → copy the hook URL → add as GitHub secret `RENDER_DEPLOY_HOOK`

---

### Step 3 — Frontend: Vercel (free tier)
1. Sign up at https://vercel.com → **Add New Project** → import your GitHub repo
2. Set **Root Directory** to `frontend`
3. Under **Environment Variables** add:
   | Key | Value |
   |-----|-------|
   | `VITE_API_URL` | your Render backend URL from Step 2 |
4. Click **Deploy** → Vercel auto-builds on every push to `main`
5. For CI/CD: go to **Account Settings → Tokens** → create token → add as GitHub secret `VERCEL_TOKEN`; also add `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` (from `.vercel/project.json` after running `npx vercel --cwd frontend` locally once)

---

### Step 4 — Redis (optional, for rate limiting)
Rate limiting **fails open** when Redis is unavailable — the app works fine without it.
If you want rate limiting in production, use **Upstash Redis** (free tier):
1. https://upstash.com → create a Redis database → copy the `REDIS_URL`
2. Add it to Render environment variables

### Database → MongoDB Atlas
Replace `MONGODB_URL` with Atlas connection string.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | **Required.** Get from console.groq.com |
| `MONGODB_URL` | `mongodb://mongo:27017` | MongoDB connection |
| `REDIS_URL` | `redis://redis:6379` | Redis connection |
| `SECRET_KEY` | — | JWT signing key (generate random) |
| `WHISPER_MODEL` | `base` | tiny/base/small/medium/large |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace sentence transformer |
| `GROQ_MODEL` | `llama3-8b-8192` | Groq model name |
| `MAX_FILE_SIZE_MB` | `500` | Upload size limit |

---

## Interview Notes — How to Explain This Project

**"What problem does your project solve?"**
> Allows users to upload any media file (PDF, audio, video) and ask natural language questions about the content. The system finds the relevant section and returns the answer with the exact timestamp to jump to in the media player.

**"What is RAG and why did you use it?"**
> RAG (Retrieval Augmented Generation) prevents hallucinations by grounding the LLM's answer in actual content. Instead of relying on training data, we retrieve the most semantically similar chunks from the document using vector search, then pass only those to the LLM as context.

**"How does the chatbot work internally?"**
> Question → HuggingFace embedding → FAISS similarity search → top-4 chunks → Groq LLM with context prompt → answer + timestamp matching.

**"How would you scale to 1000 users?"**
> Redis caching for summaries/common queries, horizontal scaling with multiple FastAPI workers behind a load balancer, async MongoDB with connection pooling, background task queue (Celery/RQ) for heavy processing like Whisper transcription.

---

## License
MIT

---

## Streaming Chat (SSE)

MediaQA supports **real-time streaming** responses via Server-Sent Events.

### Endpoint
```
POST /chat/stream
Content-Type: application/json

{ "file_id": "...", "question": "..." }
```

### SSE Frame Format
```
data: <token>           ← LLM token (incremental)
data: [META]<json>      ← timestamp + sources after full answer
data: [DONE]            ← stream complete
data: [ERROR]<msg>      ← error occurred
```

The frontend **⚡ Streaming** toggle switches between real-time streaming and buffered mode.

---

## Rate Limiting

All endpoints are protected by a **Redis sliding-window rate limiter**.

| Endpoint | IP Limit | User Limit |
|----------|----------|------------|
| `POST /chat` | 10 req/min | 20 req/min |
| `POST /chat/stream` | 10 req/min | 20 req/min |
| `POST /upload` | 10 req/min | 20 req/min |
| General | 60 req/min | 120 req/min |

Rate limit headers are returned on every response:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1712345678
```

If Redis is unavailable, rate limiting **fails open** (all requests allowed) so the app stays live.

---

## Test Coverage

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Test files and what they cover:
- `test_upload.py` — upload pipeline (PDF, audio, video, error cases, file listing)
- `test_chat.py` — RAG chat, timestamp extraction, error handling
- `test_processing.py` — unit tests for RAG, Whisper, PDF, LLM, auth, summary
- `test_streaming.py` — SSE streaming endpoint, token delivery, [META]/[DONE] frames
- `test_rate_limiting.py` — rate limiter unit tests + integration tests for 429 responses

Target: **95%+ coverage**
