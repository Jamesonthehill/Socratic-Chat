"""Private Socratic engine service used by the shared platform gateway."""
from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.schemas import ChatMessage
from platform_app import engines


app = FastAPI(title="Socratic Chat Engine", version="1.0.0")


def _require_socratic_assignment(assignment: dict[str, Any]) -> None:
    if assignment.get("tool") != "socratic":
        raise HTTPException(422, "This endpoint accepts Socratic assignments only.")


@app.middleware("http")
async def platform_service_access(request: Request, call_next):
    if request.url.path.startswith("/internal/"):
        expected = os.getenv("PLATFORM_SERVICE_TOKEN", "")
        supplied = request.headers.get("X-Platform-Service", "")
        if not expected or not secrets.compare_digest(supplied, expected):
            return JSONResponse({"detail": "Use the shared platform to access the Socratic service."}, status_code=401)
    return await call_next(request)


class AssignmentAction(BaseModel):
    assignment: dict[str, Any]
    attempt: dict[str, Any]


class MessageAction(AssignmentAction):
    content: str = Field(min_length=1, max_length=12000)
    request_id: str = Field(min_length=1, max_length=160)
    clarification_index: int | None = Field(default=None, ge=0)
    concept_check_option: int | None = Field(default=None, ge=0)
    clarification_text: bool = False


class ReflectionAction(AssignmentAction):
    reflection: str = Field(min_length=1, max_length=12000)


class PublicMessageAction(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    engine_state: dict[str, Any] = Field(default_factory=dict)
    learning_topic: str | None = Field(default=None, max_length=500)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/platform/start")
def start(body: AssignmentAction) -> dict[str, Any]:
    _require_socratic_assignment(body.assignment)
    return engines.start(body.assignment, body.attempt)


@app.post("/internal/platform/message")
def message(body: MessageAction) -> dict[str, Any]:
    _require_socratic_assignment(body.assignment)
    return engines.message(
        body.assignment,
        body.attempt,
        body.content,
        body.request_id,
        clarification_index=body.clarification_index,
        concept_check_option=body.concept_check_option,
        clarification_text=body.clarification_text,
    )


@app.post("/internal/platform/reflect")
def reflect(body: ReflectionAction) -> dict[str, Any]:
    _require_socratic_assignment(body.assignment)
    return engines.reflect(body.assignment, body.attempt, body.reflection)


@app.post("/internal/platform/complete")
def complete(body: AssignmentAction) -> dict[str, Any]:
    _require_socratic_assignment(body.assignment)
    return engines.complete(body.assignment, body.attempt)


@app.post("/internal/platform/public-message")
async def public_message(body: PublicMessageAction) -> dict[str, Any]:
    result, learning_topic = await engines.public_socratic_message(
        body.content,
        [ChatMessage(**item) for item in body.history],
        body.engine_state,
        body.learning_topic,
    )
    return {"result": result, "learning_topic": learning_topic}
