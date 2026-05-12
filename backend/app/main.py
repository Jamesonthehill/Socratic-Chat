from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, settings
from app.rag import generate_answer, ingest_file, ingest_text, retrieve, scan_raw_docs
from app.schemas import ChatRequest, ChatResponse, ConversationListResponse, ConversationResponse, DatabaseStatus, IngestResponse, RagFileListResponse, TextDocumentRequest


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


@app.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations() -> ConversationListResponse:
    if not db.is_enabled():
        return ConversationListResponse(conversations=[])
    return ConversationListResponse(conversations=db.list_conversations())


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str) -> ConversationResponse:
    if not db.is_enabled():
        return ConversationResponse(conversation_id=conversation_id, messages=[])
    return ConversationResponse(conversation_id=conversation_id, messages=db.get_messages(conversation_id))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, bool]:
    if not db.is_enabled():
        return {"deleted": False}
    return {"deleted": db.delete_conversation(conversation_id)}


@app.get("/api/documents/files", response_model=RagFileListResponse)
async def list_uploaded_files() -> RagFileListResponse:
    if not db.is_enabled():
        return RagFileListResponse(files=[])
    return RagFileListResponse(files=db.list_rag_files())


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


@app.post("/api/documents/upload", response_model=IngestResponse)
async def upload_document(request: Request) -> IngestResponse:
    try:
        form = await request.form()
    except (AssertionError, RuntimeError) as exc:
        raise HTTPException(status_code=501, detail="Install python-multipart to upload files.") from exc

    files = form.getlist("files") or form.getlist("file")
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one file to upload.")

    settings.RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    chunks_added = 0
    documents_scanned = 0
    files_stored = 0
    skipped_files: list[str] = []

    for upload in files:
        filename = Path(getattr(upload, "filename", "") or "upload.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".txt", ".md", ".pdf"}:
            skipped_files.append(filename)
            continue

        content = upload.file.read()
        target = settings.RAW_DOCS_DIR / filename
        target.write_bytes(content)

        if db.is_enabled():
            db.save_rag_file(filename, getattr(upload, "content_type", "") or "application/octet-stream", content)
            files_stored += 1

        _, added = ingest_file(target)
        documents_scanned += 1
        chunks_added += added

    if documents_scanned == 0:
        message = "No supported files were uploaded. Use .txt, .md, or .pdf."
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    conversation_id = payload.conversation_id
    history = payload.history

    if db.is_enabled():
        conversation_id = db.ensure_conversation(payload.conversation_id, payload.message)
        stored_history = db.get_messages(conversation_id, limit=8)
        history = stored_history or payload.history
        db.add_message(conversation_id, "user", payload.message)

    sources = retrieve(payload.message, top_k=payload.top_k)
    answer = await generate_answer(payload.message, history, sources)

    if db.is_enabled() and conversation_id:
        db.add_message(conversation_id, "assistant", answer)

    return ChatResponse(answer=answer, conversation_id=conversation_id or "local", sources=sources)


app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
