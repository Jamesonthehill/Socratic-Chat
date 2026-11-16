"""
This module contains all chat-related routes for the LightRAG API.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import SessionLocal
from schemas.chat import ChatRequest, ChatResponse, QIRequest, QIResponse, UIDRequest, UIDResponse, QTRequest, QTResponse, SMRequest, SMResponse, GQRequest, GQResponse, ExportRequest, ExportResponse
from schemas.topic_summary import TitleRequest, TitleResponse
from services.chat import load_memory, dump_memory, summarize_memory_controller_new, get_chat_controller, get_query_interpretation_controller, get_user_intent_controller, tweak_questions_controller, create_questions_controller, export_questions_controller, generate_title_controller
from db.models import ChatSession

router = APIRouter(
    prefix="/chat",
    tags=["chats"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_chat_routes():
    @router.post("/", response_model=ChatResponse)
    async def get_chat(payload: ChatRequest, db: Session = Depends(get_db)):
        system_message = await get_chat_controller(payload, db)
        return ChatResponse(system_message=system_message)

    @router.post("/query-interpret", response_model=QIResponse)
    async def get_query_interpretation(payload: QIRequest, db: Session = Depends(get_db)):
        result = await get_query_interpretation_controller(payload, db)
        return result

    @router.post("/user-intent", response_model=UIDResponse)
    async def get_user_intent(payload: UIDRequest, db: Session = Depends(get_db)):
        result = await get_user_intent_controller(payload, db)
        parsed = json.loads(result)
        return UIDResponse(intent=parsed.get("intent", ""), reasoning=parsed.get("reasoning", ""))

    @router.post("/summarize-memory", response_model=SMResponse)
    async def summarize_memory(payload: SMRequest, db: Session = Depends(get_db)):
        session_id = payload.session_id

        # Load session and memory
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        memory = load_memory(session.memory_state)

        # Run summarization (this modifies memory in-place)
        updated = await summarize_memory_controller_new(memory)

        if updated:
            session.memory_state = dump_memory(memory)
            db.commit()

        return SMResponse(message="Memory summarized successfully." if updated else "Not enough messages to summarize. Process Skipped.", updated=updated)

    @router.post("/tweak-single-question", response_model=QTResponse)
    async def tweak_questions(payload: QTRequest, db: Session = Depends(get_db)):
        result = await tweak_questions_controller(payload, db)
        return result

    @router.post("/create-questions", response_model=GQResponse)
    async def create_questions(payload: GQRequest, db: Session = Depends(get_db)):
        result = await create_questions_controller(payload, db)
        return result

    @router.post("/questions/export", response_model=ExportResponse)
    async def export_questions(payload: ExportRequest):
        result = await export_questions_controller(payload)
        return result

    @router.post("/title", response_model=TitleResponse)
    async def generate_title(payload: TitleRequest, db: Session = Depends(get_db)):
        result = await generate_title_controller(payload, db)
        return TitleResponse(title=result, message="Session Title generated successfully.")

    return router
