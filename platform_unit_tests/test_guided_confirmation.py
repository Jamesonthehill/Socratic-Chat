import asyncio
from types import SimpleNamespace

from app import rag
from app.classifier import _classification_from_observation
from app.schemas import ChatMessage, Source


def test_guided_confirmation_prompt_continues_current_scenario(monkeypatch):
    captured = {}

    async def complete(_key, _url, request):
        captured["request"] = request
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=(
            "Glad that helped. In the event-registration example, what acceptance criterion would help the team "
            "test the empty-results page?"
        )))])

    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Ollama", "key", "url", "model"))
    monkeypatch.setattr(rag, "chat_completion", complete)
    monkeypatch.setattr(rag, "write_llm_request_snapshot", lambda *_args: None)
    source = Source(document_id="doc", chunk_id="chunk", title="Requirements.pdf",
                    text="Acceptance criteria define the behavior to test for empty search results.", score=1.0)
    history = [
        ChatMessage(role="assistant", content="Why define acceptance criteria before development?"),
        ChatMessage(role="user", content="I don't know why?"),
        ChatMessage(role="assistant", content="They prevent misunderstandings and guide testing. Does this help clarify?"),
    ]
    answer = asyncio.run(rag.generate_answer(
        "yes, I understood", history, [source],
        classification=_classification_from_observation(message_role="understanding_claim"),
        assignment_scope=True,
        active_learning_step={
            "title": "Define acceptance criteria", "goal": "Apply acceptance criteria to an example.",
            "scenario": "A campus event search returns no results.",
            "question": "What should the team agree the page will show?",
        },
    ))
    prompt = "\n".join(message["content"] for message in captured["request"]["messages"])
    assert "continue the same example" in prompt
    assert "Do not repeat the explanation" in prompt
    assert "empty-results page?" in answer
