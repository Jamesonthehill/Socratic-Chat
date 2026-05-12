from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class Source(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    text: str
    score: float


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int = Field(default=4, ge=1, le=10)


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: list[Source] = Field(default_factory=list)


class TextDocumentRequest(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)


class IngestResponse(BaseModel):
    document_id: str | None = None
    chunks_added: int
    documents_scanned: int = 0
    files_stored: int = 0
    skipped_files: list[str] = Field(default_factory=list)
    message: str = ""


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[ChatMessage] = Field(default_factory=list)


class DatabaseStatus(BaseModel):
    enabled: bool
    connected: bool
    message: str


class RagFileSummary(BaseModel):
    file_id: str
    filename: str
    content_type: str
    file_size: int
    created_at: str


class RagFileListResponse(BaseModel):
    files: list[RagFileSummary] = Field(default_factory=list)
