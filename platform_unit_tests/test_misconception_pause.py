import asyncio
import json
from types import SimpleNamespace

from app import rag
from app.schemas import Source
from platform_app import engines


SOURCE = Source(document_id="doc", chunk_id="chunk", title="Assignment.pdf", score=1,
                text="If bread is insufficient, stop the order before requesting payment.")
PAUSED = "What should the machine check before requesting payment?"
ERROR = "The machine can charge the customer even without enough bread."


def test_misconception_pause_resumes_only_after_model_resolves_confirmation(monkeypatch):
    replies = iter([
        {"lead_in": "If a cafe has no bread, it cannot make the sandwich or charge for it.",
         "next_question": "Does that distinction make sense, or would another example help?"},
        {"lead_in": "Thanks, let's return to the order.",
         "next_question": "Before taking the dollar, what should the machine verify?",
         "misconception_resolution": "resolved"},
    ])
    requests = []

    async def complete(_key, _url, request):
        requests.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(next(replies))))])

    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Ollama", "key", "url", "model"))
    monkeypatch.setattr(rag, "chat_completion", complete)
    state = {"next_thinking_step": PAUSED}
    evaluation = SimpleNamespace(misconception=ERROR)
    context = engines._misconception_context(state, evaluation, 0)
    first = asyncio.run(rag.generate_answer(
        "Charge the customer anyway", [], [SOURCE], assignment_scope=True,
        misconception_context=context,
    ))
    engines._save_misconception_context(state, context, first, None)
    assert state["pending_misconception"]["paused_question"] == PAUSED
    assert "Do not resume or replace the paused question yet" in requests[0]["messages"][1]["content"]

    context = engines._misconception_context(state, None, 0)
    second, status = asyncio.run(rag.generate_answer(
        "Yes, I understand now", [], [SOURCE], assignment_scope=True,
        misconception_context=context, return_misconception_status=True,
    ))
    assert status == "resolved"
    assert "Before taking the dollar" in second
    assert "misconception_resolution" in requests[1]["response_format"]["json_schema"]["schema"]["required"]
    engines._save_misconception_context(state, context, second, status)
    assert "pending_misconception" not in state


def test_unresolved_confirmation_retains_pause_and_new_step_clears_it():
    state = {"next_thinking_step": PAUSED}
    context = engines._misconception_context(state, SimpleNamespace(misconception=ERROR), 0)
    engines._save_misconception_context(state, context, "Would another example help?", None)
    confirmation = engines._misconception_context(state, None, 0)
    engines._save_misconception_context(state, confirmation, "Let's look at it another way. Is that clearer?", "unresolved")
    assert state["pending_misconception"] == confirmation
    assert engines._misconception_context(state, None, 1) is None
    assert "pending_misconception" not in state


def test_student_still_confused_gets_another_explanation_without_resuming(monkeypatch):
    reply = {"lead_in": "Think of a cafe with no bread: it cannot take payment for that sandwich.",
             "next_question": "Is the payment step clearer now, or which part is still confusing?",
             "misconception_resolution": "unresolved"}
    requests = []

    async def complete(_key, _url, request):
        requests.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])

    monkeypatch.setattr(rag, "generation_client_config", lambda: ("Ollama", "key", "url", "model"))
    monkeypatch.setattr(rag, "chat_completion", complete)
    state = {"pending_misconception": {"phase": "confirm", "paused_question": PAUSED,
                                      "misconception": ERROR, "step_index": 0}}
    context = engines._misconception_context(state, None, 0)
    answer, status = asyncio.run(rag.generate_answer(
        "No, I still don't understand", [], [SOURCE], assignment_scope=True,
        misconception_context=context, return_misconception_status=True,
    ))
    assert status == "unresolved"
    assert "no bread" in answer
    assert PAUSED in requests[0]["messages"][1]["content"]
    engines._save_misconception_context(state, context, answer, status)
    assert state["pending_misconception"] == context


def test_bold_question_is_saved_as_the_next_thinking_step():
    assert engines._next_thinking_step(
        "The cafe is out of bread.\n\n**What should it do with the customer's dollar?**"
    ) == "**What should it do with the customer's dollar?**"
