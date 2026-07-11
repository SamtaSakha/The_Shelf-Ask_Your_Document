"""
Ask Your Documents — FastAPI backend.

Endpoints:
  POST   /api/documents/upload   Upload one or more documents (pdf/docx/txt/md)
  GET    /api/documents          List all indexed documents
  DELETE /api/documents/{id}     Remove a document and its chunks
  POST   /api/chat               Ask a question (RAG over uploaded documents)
  GET    /api/health             Health check (also pings Ollama)
"""
import shutil
import uuid
from pathlib import Path
from typing import List

import ollama
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, document_processor, vector_store, llm_service
from .models import (
    UploadResponse,
    DocumentInfo,
    ChatRequest,
    ChatResponse,
    SourceChunk,
    DeleteResponse,
)

app = FastAPI(title="Ask Your Documents", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


@app.get("/api/health")
def health():
    ollama_ok = True
    ollama_error = None
    try:
        ollama.Client(host=config.OLLAMA_HOST).list()
    except Exception as e:  # noqa: BLE001
        ollama_ok = False
        ollama_error = str(e)

    return {
        "status": "ok",
        "ollama_reachable": ollama_ok,
        "ollama_error": ollama_error,
        "embed_model": config.EMBED_MODEL,
        "chat_model": config.CHAT_MODEL,
    }


@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    results: List[DocumentInfo] = []

    for upload in files:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix}' for {upload.filename}. "
                f"Allowed: {sorted(ALLOWED_SUFFIXES)}",
            )

        document_id = str(uuid.uuid4())
        dest_path = config.UPLOAD_DIR / f"{document_id}{suffix}"

        with dest_path.open("wb") as f:
            shutil.copyfileobj(upload.file, f)

        try:
            text = document_processor.extract_text(dest_path)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Failed to parse {upload.filename}: {e}")

        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail=f"No extractable text found in {upload.filename} (is it a scanned/image PDF?).",
            )

        chunks = document_processor.chunk_text(text)
        vector_store.add_document_chunks(document_id, upload.filename, chunks)

        results.append(
            DocumentInfo(
                document_id=document_id,
                filename=upload.filename,
                num_chunks=len(chunks),
                char_count=len(text),
            )
        )

    return UploadResponse(documents=results)


@app.get("/api/documents", response_model=UploadResponse)
def list_documents():
    summary = vector_store.list_documents()
    docs = [
        DocumentInfo(
            document_id=doc_id,
            filename=info["filename"],
            num_chunks=info["num_chunks"],
            char_count=info["char_count"],
        )
        for doc_id, info in summary.items()
    ]
    return UploadResponse(documents=docs)


@app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str):
    deleted = vector_store.delete_document(document_id)
    for f in config.UPLOAD_DIR.glob(f"{document_id}.*"):
        f.unlink(missing_ok=True)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteResponse(document_id=document_id, deleted=deleted)


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    top_k = req.top_k or config.TOP_K

    hits = vector_store.query(
        question=req.question,
        top_k=top_k,
        document_ids=req.document_ids,
    )

    if not hits:
        return ChatResponse(
            answer=(
                "I couldn't find any uploaded documents to search. "
                "Please upload a document first, then ask your question."
            ),
            sources=[],
        )

    context_blocks = [f"[Source: {h['filename']} — chunk {h['chunk_index']}]\n{h['text']}" for h in hits]

    answer = llm_service.generate_answer(req.question, context_blocks, history=req.history)

    sources = [
        SourceChunk(
            document_id=h["document_id"],
            filename=h["filename"],
            chunk_index=h["chunk_index"],
            text=h["text"][:400] + ("..." if len(h["text"]) > 400 else ""),
            score=h["score"],
        )
        for h in hits
    ]

    return ChatResponse(answer=answer, sources=sources)


# --- Serve the frontend (static files) -------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
