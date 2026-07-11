"""
Persistent ChromaDB vector store for document chunks.

Each chunk is stored with metadata: document_id, filename, chunk_index.
Embeddings are computed via the local Ollama embedding model (see llm_service).
"""
from typing import List, Optional, Dict, Any

import chromadb

from . import config
from . import llm_service

_client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
_collection = _client.get_or_create_collection(
    name=config.COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)


def add_document_chunks(document_id: str, filename: str, chunks: List[str]) -> None:
    if not chunks:
        return

    embeddings = llm_service.embed_texts(chunks)
    ids = [f"{document_id}::{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]

    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


def query(
    question: str,
    top_k: int = config.TOP_K,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query_embedding = llm_service.embed_query(question)

    where = {"document_id": {"$in": document_ids}} if document_ids else None

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )

    hits = []
    if not results["ids"] or not results["ids"][0]:
        return hits

    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        similarity = 1 - distance  # cosine distance -> similarity
        meta = results["metadatas"][0][i]
        hits.append(
            {
                "document_id": meta["document_id"],
                "filename": meta["filename"],
                "chunk_index": meta["chunk_index"],
                "text": results["documents"][0][i],
                "score": round(float(similarity), 4),
            }
        )
    return hits


def delete_document(document_id: str) -> bool:
    existing = _collection.get(where={"document_id": document_id})
    if not existing["ids"]:
        return False
    _collection.delete(where={"document_id": document_id})
    return True


def list_documents() -> Dict[str, Dict[str, Any]]:
    """Return a summary of all indexed documents: {document_id: {filename, num_chunks}}."""
    all_items = _collection.get()
    summary: Dict[str, Dict[str, Any]] = {}
    for meta, doc_text in zip(all_items["metadatas"], all_items["documents"]):
        doc_id = meta["document_id"]
        if doc_id not in summary:
            summary[doc_id] = {
                "filename": meta["filename"],
                "num_chunks": 0,
                "char_count": 0,
            }
        summary[doc_id]["num_chunks"] += 1
        summary[doc_id]["char_count"] += len(doc_text)
    return summary
