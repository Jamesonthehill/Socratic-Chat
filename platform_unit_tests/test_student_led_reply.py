import asyncio
from types import SimpleNamespace

from app.classifier import _classification_from_observation
from app.schemas import ChatMessage, Source
from app import rag
from platform_app import engines


def test_assignment_reply_uses_student_request_not_classifier_role(monkeypatch):
    requests = []

    async def complete(_api_key, _base_url, request):
        requests.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=(
            'The assignment asks you to choose a size, check ingredients, '
            'take payment, and update the inventory.'
        )))])

    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Groq", "key", "url", "model"))
    monkeypatch.setattr(rag, "chat_completion", complete)
    monkeypatch.setattr(rag, "write_llm_request_snapshot", lambda *_args: None)
    monkeypatch.setattr(rag, "update_llm_request_snapshot", lambda *_args, **_kwargs: None)
    history = [ChatMessage(role="assistant", content="Which ingredient is missing?")]
    sources = [Source(document_id="doc", chunk_id="chunk", title="Assignment", score=0.2,
                      text="Choose a sandwich size, check ingredients, take payment, then update inventory.")]
    message = "I don't get it. Explain what I need to do in this assignment."

    answers = [asyncio.run(rag.generate_answer(
        message, history, sources,
        classification=_classification_from_observation(message_role=role),
        assignment_scope=True,
    )) for role in ("student_answer", "support_request")]

    assert answers[0] == answers[1]
    assert [request["messages"] for request in requests[:2]] == [requests[0]["messages"]] * 2
    assert all("response_format" not in request for request in requests)
    instruction = requests[0]["messages"][1]["content"]
    assert "explain its main tasks and their order" in instruction
    assert "An explanation may end without a new question" in instruction


def test_explanation_clears_old_question_even_if_classifier_called_it_an_answer():
    state = {"next_thinking_step": "Which ingredient is missing?"}
    result = engines._socratic_result(
        "Here is the assignment overview: choose a size, check ingredients, then handle payment.",
        [], state, _classification_from_observation(message_role="student_answer"),
    )
    assert result["socratic"]["next_thinking_step"] == ""


def test_guided_reply_prompt_keeps_current_example_without_inventing_progress(monkeypatch):
    requests = []

    async def complete(_api_key, _base_url, request):
        requests.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=(
            "Glad that helped. In the campus event app, what should the team inspect next?"
        )))])

    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Groq", "key", "url", "model"))
    monkeypatch.setattr(rag, "chat_completion", complete)
    monkeypatch.setattr(rag, "write_llm_request_snapshot", lambda *_args: None)
    monkeypatch.setattr(rag, "update_llm_request_snapshot", lambda *_args, **_kwargs: None)
    step = {"title": "Understanding Scrum Foundations", "goal": "Explain empiricism.",
            "scenario": "A campus event app team changes signup after student feedback.",
            "question": "How does the team adapt its plan?"}
    history = [ChatMessage(role="assistant", content="Does that clarify how empiricism works?")]
    source = Source(document_id="doc", chunk_id="chunk", title="Scrum Guide", score=0.2,
                    text="Scrum uses transparency, inspection, and adaptation.")

    answer = asyncio.run(rag.generate_answer(
        "yes it works for me", history, [source], assignment_scope=True,
        active_learning_step=step,
    ))

    assert "what should the team inspect next?" in answer
    instruction = requests[0]["messages"][1]["content"]
    assert "campus event app team" in instruction
    assert "brief confirmation" in instruction
    assert "does not prove mastery" in instruction
    assert "do not introduce a new concept" in instruction
    assert "continue the same example with one new" in instruction
    assert "Do not repeat the explanation" in instruction
