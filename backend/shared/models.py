"""Shared Pydantic models for OmniRAG."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    CODE = "code"
    VIDEO = "video"
    AUDIO = "audio"
    URL = "url"
    TEXT = "text"


class ChunkMetadata(BaseModel):
    doc_id: str
    chunk_index: int
    page_number: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    source: Optional[str] = None
    section: Optional[str] = None
    language: Optional[str] = None


class Chunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    metadata: ChunkMetadata
    embedding: Optional[list[float]] = None


class DocumentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    doc_type: DocumentType
    file_size: int = 0
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "indexed"


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    status: str
    message: str = ""


class SearchQuery(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    doc_types: Optional[list[DocumentType]] = None
    doc_ids: Optional[list[str]] = None
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    doc_id: str
    filename: str
    doc_type: DocumentType
    metadata: ChunkMetadata
    highlight: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    elapsed_ms: float


class Citation(BaseModel):
    doc_id: str
    filename: str
    chunk_id: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    text_excerpt: str
    relevance_score: float


class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    doc_ids: Optional[list[str]] = None
    stream: bool = False


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str
    reasoning: Optional[str] = None
    elapsed_ms: float


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationContext(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[ChatMessage] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
