"""Public guided demonstration using the same tutoring engine as BrainTutor."""
import asyncio
from functools import lru_cache
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import settings, rag
from app.schemas import ChatMessage
from platform_app import portfolio_engine as engine

router = APIRouter(prefix="/api/public/guided")

MATERIAL = """Code review practice guide
A pull request proposes a change for teammates to inspect before merging.
Reviewers check correctness, clarity, tests, and edge cases, including empty input.
A review comment should identify a concrete problem, explain its impact, and suggest a useful direction.
The author should ask for clarification when needed and respond to the substance of feedback.
Before merging, fix identified problems and add tests that cover the reported failure.
A passing test supports the tested behavior. It does not prove that every possible input is correct.
"""
STEPS = [
    {"title": "Understand the feedback", "goal": "Explain why a reported edge case matters.",
     "scenario": "You opened a pull request for a function that processes a list of student names. A teammate reports that it crashes when the list is empty.",
     "question": "Why should you address the empty-list case even if the function works with a populated list?"},
    {"title": "Respond constructively", "goal": "Write a constructive response to a concrete review comment.",
     "scenario": "The reviewer says, “This crashes on an empty list. Could we handle that case and add a test?” You want to keep the review useful and respectful.",
     "question": "How would you respond to the reviewer, and what would you do next?"},
    {"title": "Check the fix", "goal": "Explain how an additional test supports the fix and its limits.",
     "scenario": "You fixed the empty-list crash and added a passing empty-list test. The existing tests still pass.",
     "question": "What does the new test tell your team, and what should you still consider before merging?"},
]
CHUNKS = [{"document_id": "portfolio-guide", "chunk_id": "portfolio-guide:1",
           "title": "Code review practice guide", "text": MATERIAL}]
ASSIGNMENT = {"id": "portfolio-code-review", "tool": "socratic", "title": "Code review practice",
              "snapshot": {"config": {"guidance_mode": "guided", "tutor_mode": "socrates",
                                      "learning_steps": STEPS, "minimum_step_questions": 1}, "chunks": CHUNKS}}


@lru_cache(maxsize=1)
def indexed_material():
    return [{**CHUNKS[0], "embedding": rag.create_embeddings([MATERIAL])[0],
             "embedding_model": "text-embedding-3-small"}]


class Turn(BaseModel):
    action: Literal["start", "message", "continue", "resume", "finish"] = "message"
    message: str = Field(default="", max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=80)
    engine_state: dict = Field(default_factory=dict)
    conversation_id: str = Field(default_factory=lambda: str(uuid4()), max_length=100)


def output(messages, state, conversation_id):
    return {"messages": messages, "socratic": state, "conversation_id": conversation_id,
            "steps": [{"title": step["title"], "goal": step["goal"]} for step in STEPS],
            "material": MATERIAL}


@router.post("")
async def guided_turn(body: Turn):
    state = dict(body.engine_state)
    messages = [item.model_dump() for item in body.history]
    index = min(max(int(state.get("learning_step_index") or 0), 0), len(STEPS) - 1)
    if body.action == "start":
        initial = engine.start(ASSIGNMENT, {})
        return output(initial["messages"], initial["socratic"], body.conversation_id)
    if not messages:
        raise HTTPException(409, "Start the demo first.")
    if body.action == "resume":
        detour = state.pop("learning_detour", {})
        question = str(detour.get("question") or "")
        if not question:
            raise HTTPException(409, "There is no paused question.")
        state["next_thinking_step"] = question
        for key in ("learning_topic", "stable_concept", "active_concept"):
            state[key] = detour.get(key)
        messages.append({"role": "assistant", "content":
            f"Okay, let’s apply what you just learned.\n\n{detour.get('scenario') or STEPS[index]['scenario']}\n\n{question}"})
        return output(messages, state, body.conversation_id)
    if body.action == "continue":
        if not state.get("step_readiness", {}).get("ready"):
            raise HTTPException(409, "Discuss this step with the tutor first.")
        if index >= len(STEPS) - 1:
            raise HTTPException(409, "Summarize your learning to finish.")
        index += 1
        step = STEPS[index]
        state.update(learning_step_index=index, learning_topic=step["title"],
                     next_thinking_step=step["question"], step_started_at_message_count=len(messages) + 1)
        for key in ("learning_detour", "step_readiness", "pending_misconception", "stable_concept", "active_concept"):
            state.pop(key, None)
        messages.append({"role": "assistant", "content": f"Step {index + 1}: {step['title']}\n\n{step['scenario']}\n\n{step['question']}"})
        return output(messages, state, body.conversation_id)
    if not body.message.strip():
        raise HTTPException(422, "Enter a message.")
    if not settings.OPENAI_API_KEY:
        raise HTTPException(503, "The demo’s OpenAI connection is awaiting server configuration.")
    attempt = {"id": body.conversation_id, "messages": messages, "engine_state": {"socratic": state}}
    token = settings.PORTFOLIO_OPENAI.set(True)
    try:
        chunks = await asyncio.to_thread(indexed_material)
        assignment = {**ASSIGNMENT, "snapshot": {**ASSIGNMENT["snapshot"], "chunks": chunks}}
        if body.action == "finish":
            if index != len(STEPS) - 1 or not state.get("step_readiness", {}).get("ready"):
                raise HTTPException(409, "Complete the learning steps first.")
            result = await engine._socratic_reflection(assignment, attempt, body.message)
            result["socratic"]["phase"] = "completed"
        else:
            result = await engine._socratic_message(assignment, attempt, body.message)
    finally:
        settings.PORTFOLIO_OPENAI.reset(token)
    messages.extend([{"role": "user", "content": body.message}, {"role": "assistant", "content": result["reply"]}])
    return output(messages, result["socratic"], body.conversation_id)
