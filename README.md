# Ask Your Documents

An AI-powered document Q&A system. Upload one or more documents (PDF, DOCX, TXT,
MD), then ask natural-language questions and get accurate, context-aware
answers with cited source excerpts — powered entirely by **local, open-source
models via [Ollama](https://ollama.com)**. No API keys, no cloud costs.

<p>
  <img alt="stack" src="https://img.shields.io/badge/backend-FastAPI-009688">
  <img alt="stack" src="https://img.shields.io/badge/vector%20store-ChromaDB-6E56CF">
  <img alt="stack" src="https://img.shields.io/badge/LLM-Ollama%20(local)-1B1F24">
</p>

## How it works (RAG pipeline)

```
 ┌────────────┐   parse    ┌──────────┐   embed    ┌────────────┐
 │  Upload     │ ─────────▶ │  Chunk    │ ─────────▶ │  ChromaDB   │
 │  PDF/DOCX/  │  pypdf /   │  (~1000   │  Ollama    │  (persisted │
 │  TXT/MD     │  docx      │  chars,   │  embeddings│  vector DB) │
 └────────────┘            │  150 ovlp)│            └─────┬──────┘
                                                            │
 User question ──▶ embed question ──▶ cosine similarity search (top-k)
                                                            │
                                                            ▼
                                          ┌────────────────────────────┐
                                          │ Retrieved chunks + question │
                                          │  → Ollama chat model (RAG   │
                                          │  prompt, grounded answer)   │
                                          └────────────┬───────────────┘
                                                        ▼
                                          Answer + cited source chunks
```

1. **Document parsing** — `pypdf` for PDFs, `python-docx` for Word docs, raw
   read for `.txt`/`.md`.
2. **Chunking** — paragraph-aware sliding window (~1000 characters, 150
   character overlap) so answers can cite coherent excerpts rather than
   arbitrary byte ranges.
3. **Embeddings** — each chunk (and later, each question) is embedded with
   Ollama's `nomic-embed-text` model.
4. **Vector store** — embeddings are persisted in a local **ChromaDB**
   collection (`./data/chroma`), with metadata (`document_id`, `filename`,
   `chunk_index`) attached to every chunk so retrieval can be scoped to
   specific documents.
5. **Retrieval-Augmented Generation** — on each question, the top-k most
   similar chunks are retrieved and injected into a system-prompted request
   to a local Ollama chat model (`llama3.1` by default), which is instructed
   to answer **only** from the provided context and to say so when the
   context is insufficient.
6. **Response** — the generated answer is returned together with the source
   chunks (filename, chunk index, similarity score) so the user can verify
   where each answer came from.

## Tech stack

| Layer            | Choice                                              |
|-------------------|-----------------------------------------------------|
| Backend API       | Python, FastAPI                                     |
| Document parsing  | pypdf, python-docx                                  |
| Embeddings + LLM  | Ollama (local, no API key) — `nomic-embed-text` + `llama3.1` |
| Vector database   | ChromaDB (persistent, local file store)              |
| Frontend          | Vanilla HTML/CSS/JS (no build step), served by FastAPI |

## Project structure

```
ask-your-documents/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI routes
│   │   ├── config.py             # env-driven settings
│   │   ├── models.py             # Pydantic request/response schemas
│   │   ├── document_processor.py # parsing + chunking
│   │   ├── vector_store.py       # ChromaDB wrapper
│   │   └── llm_service.py        # Ollama embeddings + chat
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/                         # created at runtime (chroma db + uploads)
├── demo/                         # place demo video/screenshots here
└── README.md
```

## Setup

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running locally

### 2. Install Ollama models

```bash
# Chat model used to generate answers
ollama pull llama3.1

# Embedding model used for indexing + retrieval
ollama pull nomic-embed-text
```

Make sure the Ollama server is running (it usually starts automatically after
install; otherwise run `ollama serve` in a terminal).

### 3. Clone and set up the backend

```bash
git clone <this-repo-url>
cd ask-your-documents/backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # defaults work out of the box
```

### 4. Run the app

```bash
# from backend/
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — the FastAPI backend serves the frontend
directly, so there's nothing else to start.

### 5. Use it

1. Drag a PDF/DOCX/TXT/MD file onto the shelf (left panel) — it's parsed,
   chunked, embedded, and indexed automatically.
2. Upload as many documents as you like. Uncheck a document's "include in
   search" box to exclude it from a particular question.
3. Ask a question in the chat box. The answer streams back with the source
   excerpts and similarity scores it was grounded in.

## Configuration

All settings live in `backend/.env` (see `.env.example`):

| Variable          | Default              | Description                                  |
|-------------------|----------------------|-----------------------------------------------|
| `OLLAMA_HOST`     | `http://localhost:11434` | Ollama server URL                        |
| `EMBED_MODEL`     | `nomic-embed-text`   | Embedding model                               |
| `CHAT_MODEL`      | `llama3.1`           | Chat/generation model                         |
| `CHUNK_SIZE`      | `1000`               | Max characters per chunk                      |
| `CHUNK_OVERLAP`   | `150`                | Character overlap between chunks              |
| `TOP_K`           | `5`                  | Number of chunks retrieved per question       |
| `DATA_DIR`        | `./data`             | Where uploads + the Chroma DB are persisted   |

Want a smaller/faster model? Swap `CHAT_MODEL` for `llama3.2` or `phi3`, or
`EMBED_MODEL` for `mxbai-embed-large` — just `ollama pull` it first.

## API reference

| Method | Endpoint                        | Description                              |
|--------|----------------------------------|-------------------------------------------|
| POST   | `/api/documents/upload`          | Upload one or more files (multipart)      |
| GET    | `/api/documents`                 | List indexed documents                    |
| DELETE | `/api/documents/{document_id}`   | Remove a document and its chunks          |
| POST   | `/api/chat`                      | Ask a question (RAG)                      |
| GET    | `/api/health`                    | Health check (also pings Ollama)          |

Example `POST /api/chat` body:

```json
{
  "question": "What was the total revenue in Q3?",
  "document_ids": null,
  "top_k": 5
}
```

Interactive API docs are available at `http://localhost:8000/docs` once the
server is running.

## Design notes / things worth knowing

- **Everything runs locally.** No OpenAI/Anthropic API keys are required —
  the entire pipeline (embeddings + generation) runs against your local
  Ollama instance, so it works offline and has no per-token cost.
- **Grounded answers.** The system prompt explicitly instructs the model to
  answer only from retrieved context and to admit when it doesn't know,
  reducing hallucination.
- **Scoped retrieval.** Each chunk carries its source document's ID, so
  questions can be answered against all documents or a hand-picked subset.
- **Persistence.** ChromaDB persists to disk (`data/chroma`), so uploaded
  documents survive a server restart.

## Possible extensions

- Streaming token-by-token responses (Ollama supports streaming; the
  frontend would need an SSE/WebSocket client).
- Swap ChromaDB for a hosted vector DB (Pinecone/Weaviate) for multi-user
  deployments.
- Add OCR (e.g. `pytesseract`) for scanned/image-only PDFs.
- Multi-user auth and per-user document isolation.

## Demo

See `demo/`  https://drive.google.com/file/d/15z-LbuvH7djEhg-qIXcTF5XnvvbsZmaa/view?usp=sharing  for a walkthrough video showing document upload and multiple
successful Q&A interactions.

