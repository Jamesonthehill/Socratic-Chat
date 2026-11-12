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
        "final_comment": "Review helps the team spot defects before merging. Keep testing too.",
        "final_emphasis": "Review helps the team spot defects before merging.",
        "misconception_correction": "A review does not guarantee bug-free code.",
        "concepts_to_revisit": revisits,
        "scenario_wrap_up": "The teammate reviews the change before merging.",
        "opening_answer": "Review helps teammates inspect a change.",
    }


def generate(monkeypatch, revisits):
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps(completion_payload(revisits))))])
    chat = AsyncMock(return_value=response)
    monkeypatch.setattr(rag, "completion_client_config", lambda: ("OpenAI", "test", "http://localhost", "gpt-4.1-mini"))
    monkeypatch.setattr(rag, "completion_chat_completion", chat)
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
    assert summary.final_comment == "**Review helps the team spot defects before merging.** Keep testing too."
    request = chat.await_args.args[2]
    assert request["model"] == "gpt-4.1-mini"
    assert "exact, contiguous quote" in request["messages"][0]["content"]


def test_final_feedback_discards_invented_quotes_and_sources(monkeypatch):
    summary, _ = generate(monkeypatch, [
        {"student_quote": "Review always catches every defect.", "correction": "No guarantee.", "source_title": "Code review guide"},
        {"student_quote": "Review guarantees no bugs.", "correction": "No guarantee.", "source_title": "Invented source"},
    ])
    assert summary.concepts_to_revisit == []


def test_step_review_requires_quotes_from_the_same_step(monkeypatch):
    payload = completion_payload([])
    payload.update({
        "step_reviews": [{
            "step_index": 0,
            "understood": [
                {"explanation": "You identified the limit of review.", "student_quotes": ["Review helps but tests are needed."]},
                {"explanation": "Invented understanding.", "student_quotes": ["I understand everything."]},
            ],
            "clarified": [{"explanation": "Progress without earlier evidence.", "student_quotes": ["Review helps but tests are needed."]}],
            "revisit": [],
        }],
        "next_action": "Practice identifying a useful test.",
    })
    monkeypatch.setattr(rag, "completion_client_config", lambda: ("OpenAI", "test", "http://localhost", "gpt-4.1-mini"))
    monkeypatch.setattr(rag, "completion_chat_completion", AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])))
    summary = asyncio.run(rag.generate_completion_summary(
        "Why review?", "Review helps but tests are needed.",
        [ChatMessage(role="user", content="Review helps but tests are needed.")],
        [SOURCE], None, "Review helps.", step_conversations=[{
            "step_index": 0, "title": "Review", "goal": "Understand review limits",
            "messages": [{"role": "user", "content": "Review helps but tests are needed."}],
        }],
    ))
    assert len(summary.step_reviews[0].understood) == 1
    assert not summary.step_reviews[0].clarified
    assert summary.next_action == "Practice identifying a useful test."


def test_completion_routing_is_independent_of_tutor_and_other_activities(monkeypatch):
    monkeypatch.setattr(rag.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(rag.settings, "SOCRATIC_COMPLETION_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr(rag.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(rag.settings, "SOCRATIC_TUTOR_PROVIDER", "groq")
    config = rag.completion_client_config()
    assert config[0] == "OpenAI"
    assert config[3] == "gpt-4.1-mini"
    assert rag.settings.LLM_PROVIDER == "groq"
    monkeypatch.setattr(rag.settings, "OPENAI_API_KEY", "")
    assert rag.completion_client_config() is None
