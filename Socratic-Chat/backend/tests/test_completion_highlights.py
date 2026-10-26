"""Final feedback highlights only student wording supported by course evidence."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import rag
from app.schemas import ChatMessage, Source


SOURCE = Source(document_id="doc", chunk_id="chunk", title="Code review guide",
                text="Review can identify defects, but cannot guarantee a change has no bugs.", score=1)


def completion_payload(revisits):
    return {
        "final_comment": "You described why teammates review changes.",
        "misconception_correction": "A review does not guarantee bug-free code.",
        "concepts_to_revisit": revisits,
        "scenario_wrap_up": "The teammate reviews the change before merging.",
        "opening_answer": "Review helps teammates inspect a change.",
    }


def generate(monkeypatch, revisits):
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps(completion_payload(revisits))))])
    chat = AsyncMock(return_value=response)
    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Ollama", "test", "http://localhost", "test-model"))
    monkeypatch.setattr(rag, "chat_completion", chat)
    summary = asyncio.run(rag.generate_completion_summary(
        "How does review help?", "Review guarantees no bugs.",
        [ChatMessage(role="user", content="Review guarantees no bugs.")],
        [SOURCE], None, "Review guarantees no bugs.",
    ))
    return summary, chat


def test_final_feedback_keeps_exact_student_quote_and_course_source(monkeypatch):
    summary, chat = generate(monkeypatch, [{
        "student_quote": "Review guarantees no bugs.",
        "correction": "Review helps find problems but cannot guarantee no bugs.",
        "source_title": "Code review guide",
    }])
    assert summary.concepts_to_revisit[0].student_quote == "Review guarantees no bugs."
    assert summary.concepts_to_revisit[0].source_title == "Code review guide"
    request = chat.await_args.args[2]
    assert "exact, contiguous quote" in request["messages"][0]["content"]


def test_final_feedback_discards_invented_quotes_and_sources(monkeypatch):
    summary, _ = generate(monkeypatch, [
        {"student_quote": "Review always catches every defect.", "correction": "No guarantee.", "source_title": "Code review guide"},
        {"student_quote": "Review guarantees no bugs.", "correction": "No guarantee.", "source_title": "Invented source"},
    ])
    assert summary.concepts_to_revisit == []
