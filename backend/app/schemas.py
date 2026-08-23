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


class AuthConfigResponse(BaseModel):
    email_verification_required: bool
    auth_mode: str
    password_auth_enabled: bool
    school_domain: str | None = None
    github_account_required: bool = False
    github_oauth_configured: bool = False


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class EmailCodeResponse(BaseModel):
    message: str
    expires_in_minutes: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=200)
    verification_code: str | None = Field(default=None, min_length=6, max_length=6)


class GoogleClientConfigResponse(BaseModel):
    client_id: str
    hosted_domain: str | None = None


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=20)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str | None = None
    email: str
    github_connected: bool = False
    github_username: str | None = None


class AuthResponse(BaseModel):
    user: UserProfile
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class SessionRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class CurrentUserResponse(BaseModel):
    user: UserProfile


class GitHubAuthorizeResponse(BaseModel):
    authorize_url: str
