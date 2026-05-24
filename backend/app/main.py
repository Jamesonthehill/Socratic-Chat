from __future__ import annotations

from pathlib import Path
import json
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, settings
from app.classifier import classify_message
from app.rag import generate_answer, ingest_file, ingest_text, retrieve, retrieve_by_titles, retrieve_overview, scan_raw_docs
from app.schemas import AuthResponse, ChatRequest, ChatResponse, ConversationListResponse, ConversationResponse, DatabaseStatus, EmailCodeRequest, EmailCodeResponse, GoogleAuthRequest, GoogleClientConfigResponse, IngestResponse, LoginRequest, RagFileListResponse, RegisterRequest, TextDocumentRequest


app = FastAPI(title="My RAG Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    db.init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/db/status", response_model=DatabaseStatus)
async def database_status() -> DatabaseStatus:
    connected, message = db.check_status()
    return DatabaseStatus(enabled=db.is_enabled(), connected=connected, message=message)


def _current_user_id(request: Request) -> str | None:
    user_id = request.headers.get("x-user-id")
    return user_id.strip() if user_id else None


def _send_verification_email(email: str, code: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise HTTPException(
            status_code=503,
            detail="Email verification is not configured. Add SMTP settings to .env.",
        )

    message = EmailMessage()
    message["Subject"] = "Your RAG Chatbot verification code"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        f"Your verification code is {code}.\n\n"
        f"This code expires in {settings.EMAIL_CODE_EXPIRY_MINUTES} minutes."
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not send verification email: {exc}") from exc


@app.post("/api/auth/send-verification-code", response_model=EmailCodeResponse)
async def send_verification_code(payload: EmailCodeRequest) -> EmailCodeResponse:
    if not db.is_enabled():
        raise HTTPException(status_code=503, detail="PostgreSQL is not connected.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.save_email_verification_code(payload.email, code, settings.EMAIL_CODE_EXPIRY_MINUTES)
    _send_verification_email(payload.email, code)
    return EmailCodeResponse(
        message="Verification code sent. Please check your email.",
        expires_in_minutes=settings.EMAIL_CODE_EXPIRY_MINUTES,
    )


@app.post("/api/auth/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    if not db.is_enabled():
        raise HTTPException(status_code=503, detail="PostgreSQL is not connected.")
    if not db.verify_email_code(payload.email, payload.verification_code):
        raise HTTPException(status_code=400, detail="Verification code is wrong or expired.")
    try:
        user = db.create_user(payload.username, payload.email, payload.password)
    except Exception as exc:
        detail = str(exc)
        if "users_username_key" in detail or "users_email_key" in detail or "duplicate key" in detail:
            raise HTTPException(status_code=409, detail="That username or email is already registered.") from exc
        raise
    return AuthResponse(user=user)


@app.get("/api/auth/google/config", response_model=GoogleClientConfigResponse)
async def google_client_config() -> GoogleClientConfigResponse:
    return GoogleClientConfigResponse(client_id=settings.GOOGLE_CLIENT_ID)


def _verify_google_credential(credential: str) -> dict[str, str]:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")

    query = urlencode({"id_token": credential})
    try:
        with urlopen(f"https://oauth2.googleapis.com/tokeninfo?{query}", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Could not verify Google sign-in: {exc}") from exc

    if data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google sign-in audience does not match this app.")
    if data.get("email_verified") not in {"true", True}:
        raise HTTPException(status_code=401, detail="Google email is not verified.")
    if not data.get("email") or not data.get("sub"):
        raise HTTPException(status_code=401, detail="Google sign-in response is missing account details.")

    return {"email": data["email"], "sub": data["sub"], "name": data.get("name") or data["email"].split("@", 1)[0]}


@app.post("/api/auth/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest) -> AuthResponse:
    if not db.is_enabled():
        raise HTTPException(status_code=503, detail="PostgreSQL is not connected.")

    profile = _verify_google_credential(payload.credential)
    user = db.find_or_create_google_user(profile["email"], profile["sub"], profile.get("name"))
    return AuthResponse(user=user)


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    if not db.is_enabled():
        raise HTTPException(status_code=503, detail="PostgreSQL is not connected.")
    user = db.authenticate_user(payload.identifier, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email/username or password is wrong.")
    return AuthResponse(user=user)


@app.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(request: Request) -> ConversationListResponse:
    if not db.is_enabled():
        return ConversationListResponse(conversations=[])
    user_id = _current_user_id(request)
    return ConversationListResponse(conversations=db.list_conversations(user_id=user_id))


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, request: Request) -> ConversationResponse:
    if not db.is_enabled():
        return ConversationResponse(conversation_id=conversation_id, messages=[])
    user_id = _current_user_id(request)
    if not db.conversation_belongs_to(conversation_id, user_id):
        raise HTTPException(status_code=404, detail="Chat not found.")
    return ConversationResponse(conversation_id=conversation_id, messages=db.get_messages(conversation_id))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request) -> dict[str, bool]:
    if not db.is_enabled():
        return {"deleted": False}
    user_id = _current_user_id(request)
    if not db.conversation_belongs_to(conversation_id, user_id):
        return {"deleted": False}
    return {"deleted": db.delete_conversation(conversation_id)}


@app.get("/api/documents/files", response_model=RagFileListResponse)
async def list_uploaded_files(request: Request) -> RagFileListResponse:
    if not db.is_enabled():
        return RagFileListResponse(files=[])
    user_id = _current_user_id(request)
    conversation_id = request.query_params.get("conversation_id")
    try:
        files = db.list_rag_files(conversation_id=conversation_id, user_id=user_id)
    except TypeError:
        files = db.list_rag_files(conversation_id=conversation_id)
    return RagFileListResponse(files=files)


@app.get("/api/documents/files/{file_id}/download")
async def download_uploaded_file(file_id: str, request: Request) -> Response:
    if not db.is_enabled():
        raise HTTPException(status_code=503, detail="PostgreSQL is not connected.")

    user_id = _current_user_id(request)
    file = db.get_rag_file(file_id, user_id=user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found.")

    filename = str(file["filename"])
    content_type = str(file["content_type"] or "application/octet-stream")
    quoted_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
        "Content-Length": str(file["file_size"]),
    }
    return Response(content=file["content"], media_type=content_type, headers=headers)


@app.post("/api/documents/text", response_model=IngestResponse)
async def add_text_document(payload: TextDocumentRequest) -> IngestResponse:
    doc_id, chunks_added = ingest_text(payload.title, payload.text)
    message = "Text added to the knowledge base." if chunks_added else "That text was already indexed."
    return IngestResponse(document_id=doc_id, chunks_added=chunks_added, documents_scanned=1, message=message)


@app.post("/api/documents/scan", response_model=IngestResponse)
async def scan_documents() -> IngestResponse:
    documents_scanned, chunks_added, skipped_files = scan_raw_docs()
    if documents_scanned == 0:
        message = "No .txt, .md, or .pdf files found in backend/data/raw_docs."
    elif chunks_added == 0:
        message = "Documents were found, but no new chunks were added. They may already be indexed."
    else:
        message = "Documents scanned successfully."
    return IngestResponse(
        chunks_added=chunks_added,
        documents_scanned=documents_scanned,
        skipped_files=skipped_files,
        message=message,
    )


def _chat_title_from_uploads(files: list[object]) -> str:
    filenames: list[str] = []
    seen = set()
    for upload in files:
        filename = Path(getattr(upload, "filename", "") or "upload.txt").name
        if not filename or filename in seen:
            continue
        seen.add(filename)
        filenames.append(filename)

    if not filenames:
        return "Uploaded documents"

    if len(filenames) == 1:
        return filenames[0]

    return f"{filenames[0]} + {len(filenames) - 1} more"


@app.post("/api/documents/upload", response_model=IngestResponse)
async def upload_document(request: Request) -> IngestResponse:
    try:
        form = await request.form()
    except (AssertionError, RuntimeError) as exc:
        raise HTTPException(status_code=501, detail="Install python-multipart to upload files.") from exc

    files = form.getlist("files") or form.getlist("file")
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one file to upload.")

    conversation_id = form.get("conversation_id")
    user_id = _current_user_id(request)
    chat_title = _chat_title_from_uploads(files)
    if conversation_id and db.is_enabled():
        db.ensure_conversation(str(conversation_id), chat_title, user_id=user_id)
        if hasattr(db, "set_conversation_title"):
            db.set_conversation_title(str(conversation_id), chat_title, user_id=user_id)

    settings.RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    chunks_added = 0
    documents_scanned = 0
    files_stored = 0
    skipped_files: list[str] = []

    store_suffixes = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    rag_suffixes = {".txt", ".md", ".pdf"}

    for upload in files:
        filename = Path(getattr(upload, "filename", "") or "upload.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in store_suffixes:
            skipped_files.append(filename)
            continue

        content = upload.file.read()
        target = settings.RAW_DOCS_DIR / filename
        target.write_bytes(content)

        if db.is_enabled():
            db.save_rag_file(
                filename,
                getattr(upload, "content_type", "") or "application/octet-stream",
                content,
                str(conversation_id) if conversation_id else None,
                user_id=user_id,
            )
            files_stored += 1

        added = 0
        if suffix in rag_suffixes:
            _, added = ingest_file(target, str(conversation_id) if conversation_id else None)
            documents_scanned += 1
        chunks_added += added

    if documents_scanned == 0:
        message = "No supported files were uploaded. Use .txt, .md, .pdf, or common image files."
    elif chunks_added == 0:
        message = "Uploaded file(s) were already indexed."
    else:
        message = "Uploaded file(s) added to the knowledge base."

    return IngestResponse(
        chunks_added=chunks_added,
        documents_scanned=documents_scanned,
        files_stored=files_stored,
        skipped_files=skipped_files,
        message=message,
    )



def _normalise_text(message: str) -> str:
    return " ".join(message.lower().strip().split())


def _is_file_status_question(message: str) -> bool:
    text = _normalise_text(message)
    words = text.split()

    # Keep real content questions in the RAG path. For example:
    # "what is machine learning in this paper?" should retrieve from the PDF,
    # not merely report that a PDF exists.
    content_question_patterns = [
        "what is",
        "what are",
        "explain",
        "summarize",
        "define",
        "according to",
        "why",
        "how does",
        "how do",
        "compare",
    ]
    file_listing_patterns = [
        "what file",
        "what files",
        "which file",
        "which files",
        "what document",
        "what documents",
        "which document",
        "which documents",
        "what pdf",
        "which pdf",
        "file name",
        "filename",
        "name of the file",
        "what is the file name",
        "what's the file name",
        "which file name",
        "file we looked at",
        "file we are looking at",
        "what kind of list",
        "what kind of lists",
        "what list",
        "what lists",
    ]

    if any(pattern in text for pattern in content_question_patterns) and not any(
        pattern in text for pattern in file_listing_patterns
    ):
        return False

    status_patterns = [
        "do you have a document",
        "do you have any document",
        "do you have documents",
        "do you have a file",
        "do you have any file",
        "do you see a file",
        "do you see my file",
        "can you see the file",
        "can you see my file",
        "can you read the file",
        "what is the file name",
        "what's the file name",
        "what file are we looking at",
        "what file did i upload",
        "what files did i upload",
        "what documents did i upload",
        "which file did i upload",
        "which documents did i upload",
        "list uploaded files",
        "list my files",
        "show uploaded files",
        "show my documents",
        "show my files",
        "did i upload",
        "is there a file",
        "is there any file",
        "uploaded files",
        "uploaded documents",
        "for now",
    ]
    if any(pattern in text for pattern in status_patterns):
        return True

    file_words = {"file", "files", "document", "documents", "pdf", "paper", "papers"}
    list_words = {"list", "lists", "show", "see", "have", "uploaded"}
    if file_words.intersection(words) and list_words.intersection(words):
        return True

    # Short phrases like "privacy risks pdf" or "machine learning pdf?" are
    # usually the user checking which uploaded document the chatbot sees.
    if len(words) <= 5 and file_words.intersection(words):
        return True

    return False


def _is_start_study_request(message: str) -> bool:
    text = _normalise_text(message)
    study_words = ["study", "start", "learn", "review", "practice"]
    file_refs = ["this file", "this document", "this pdf", "uploaded file", "uploaded document", "the file"]
    return any(word in text for word in study_words) and any(ref in text for ref in file_refs)


def _unique_file_names(files: list[dict[str, object]]) -> list[str]:
    names: list[str] = []
    seen = set()
    for file in files:
        name = str(file.get("filename", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names




def _small_status_answer(files: list[dict[str, object]], message: str) -> str | None:
    text = _normalise_text(message)
    status_patterns = [
        "is it going well",
        "it's going well",
        "is this working",
        "does it work",
        "are we good",
        "are you ready",
    ]
    if not any(pattern in text for pattern in status_patterns):
        return None

    names = _unique_file_names(files)
    if not names:
        return "Not yet. I do not see an uploaded file in this chat."

    if len(names) == 1:
        return f"Yes. I can see {names[0]} in this chat. Ask me a specific question about it, or ask for a summary."

    return f"Yes. I can see {len(names)} files in this chat: {', '.join(names[:5])}."

def _file_state_answer(files: list[dict[str, object]], message: str) -> str | None:
    wants_status = _is_file_status_question(message)
    wants_study_start = _is_start_study_request(message)
    if not wants_status and not wants_study_start:
        return None

    names = _unique_file_names(files)
    if not names:
        return "I do not see any uploaded files in this chat yet. Attach a .txt, .md, or .pdf file first."

    if len(names) == 1:
        return (
            f"Yes, I see your uploaded file: {names[0]}. "
            "We can start with a summary, key concepts, or practice questions. Which one do you prefer?"
        )

    preview = ", ".join(names[:5])
    return (
        f"Yes, I see these uploaded files: {preview}. "
        "Which one should we focus on first?"
    )



def _is_document_overview_question(message: str) -> bool:
    text = _normalise_text(message)
    overview_patterns = [
        "topic",
        "main topic",
        "main idea",
        "what is this about",
        "what's this about",
        "what is the document about",
        "what is this document about",
        "what is this paper about",
        "what's the paper about",
        "summarize",
        "summary",
        "overview",
    ]
    return any(pattern in text for pattern in overview_patterns)


OFF_TOPIC_TERMS = {"messi", "ronaldo", "soccer", "football", "nba", "weather", "movie", "restaurant"}


def _off_topic_answer(message: str) -> str | None:
    words = set(_normalise_text(message).replace("?", "").split())
    if not words.intersection(OFF_TOPIC_TERMS):
        return None
    return (
        "That question is outside the uploaded documents for this chat, "
        "so I should not answer it from the RAG workspace."
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    conversation_id = payload.conversation_id
    history = payload.history
    user_id = _current_user_id(request)

    if db.is_enabled():
        conversation_id = db.ensure_conversation(payload.conversation_id, payload.message, user_id=user_id)
        stored_history = db.get_messages(conversation_id, limit=8)
        history = stored_history or payload.history
        db.add_message(conversation_id, "user", payload.message)

        off_topic_answer = _off_topic_answer(payload.message)
        if off_topic_answer:
            if hasattr(db, "clear_pending_clarification"):
                db.clear_pending_clarification(conversation_id)
            db.add_message(conversation_id, "assistant", off_topic_answer)
            return ChatResponse(answer=off_topic_answer, conversation_id=conversation_id, sources=[])

        pending = db.get_pending_clarification(conversation_id) if hasattr(db, "get_pending_clarification") else None
        if pending:
            combined_query = f"{pending['original_question']} {payload.message}".strip()
            if hasattr(db, "clear_pending_clarification"):
                db.clear_pending_clarification(conversation_id)
            sources = retrieve(combined_query, top_k=payload.top_k, conversation_id=conversation_id)
            answer = await generate_answer(combined_query, history, sources)
            if answer.lower().startswith("i do not know from your uploaded notes"):
                sources = []
            db.add_message(conversation_id, "assistant", answer)
            return ChatResponse(answer=answer, conversation_id=conversation_id, sources=sources)

    current_files = db.list_rag_files(conversation_id=conversation_id, user_id=user_id) if db.is_enabled() and conversation_id else []
    file_state_answer = _file_state_answer(current_files, payload.message) or _small_status_answer(current_files, payload.message)
    if file_state_answer:
        if db.is_enabled() and conversation_id:
            if hasattr(db, "clear_pending_clarification"):
                db.clear_pending_clarification(conversation_id)
            db.add_message(conversation_id, "assistant", file_state_answer)
        return ChatResponse(answer=file_state_answer, conversation_id=conversation_id or "local", sources=[])

    classification = await classify_message(payload.message, history)

    if classification.needs_clarification:
        answer = classification.clarification_question or "Could you clarify what you want to know?"
        if db.is_enabled() and conversation_id:
            if hasattr(db, "set_pending_clarification"):
                db.set_pending_clarification(conversation_id, payload.message, classification.target)
            db.add_message(conversation_id, "assistant", answer)
        return ChatResponse(answer=answer, conversation_id=conversation_id or "local", sources=[])

    if classification.direct_answer:
        answer = classification.direct_answer
        if db.is_enabled() and conversation_id:
            if hasattr(db, "clear_pending_clarification"):
                db.clear_pending_clarification(conversation_id)
            db.add_message(conversation_id, "assistant", answer)
        return ChatResponse(answer=answer, conversation_id=conversation_id or "local", sources=[])

    query = classification.rewritten_query or payload.message
    sources = retrieve(query, top_k=payload.top_k, conversation_id=conversation_id)
    if not sources and current_files:
        file_names = _unique_file_names(current_files)
        sources = retrieve_by_titles(query, file_names, top_k=payload.top_k)
    if not sources and current_files and _is_document_overview_question(payload.message):
        sources = retrieve_overview(conversation_id=conversation_id, top_k=payload.top_k)
    answer = await generate_answer(query, history, sources)
    if answer.lower().startswith("i do not know from your uploaded notes"):
        sources = []

    if db.is_enabled() and conversation_id:
        if hasattr(db, "clear_pending_clarification"):
            db.clear_pending_clarification(conversation_id)
        db.add_message(conversation_id, "assistant", answer)

    return ChatResponse(answer=answer, conversation_id=conversation_id or "local", sources=sources)

app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
