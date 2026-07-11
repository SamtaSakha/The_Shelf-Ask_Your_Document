"""Pydantic schemas used across the API."""
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    num_chunks: int
    char_count: int


class UploadResponse(BaseModel):
    documents: List[DocumentInfo]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Restrict retrieval to these document IDs. Omit to search all uploaded documents.",
    )
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    history: Optional[List[dict]] = Field(
        default=None,
        description="Optional prior turns: [{role: 'user'|'assistant', content: str}, ...]",
    )


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
