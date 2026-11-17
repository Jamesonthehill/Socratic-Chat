from contextlib import contextmanager
from uuid import uuid4

import pytest

from platform_app import routes
from platform_app.routes import merge_inline_clarification


def test_inline_clarification_keeps_choice_in_original_student_message():
    attempt = {"messages": [
        {"role": "assistant", "content": "What is the Sprint Goal?"},
        {"role": "user", "content": "What does that mean?"},
    ]}

    assert merge_inline_clarification(attempt, "What does that mean?", "In this assignment")
    assert attempt["messages"][-1]["content"] == (
        "What does that mean?\n\nClarification: In this assignment"
    )
    assert len(attempt["messages"]) == 2


def test_inline_clarification_does_not_rewrite_an_unrelated_turn():
    attempt = {"messages": [{"role": "user", "content": "A different question"}]}
    assert not merge_inline_clarification(attempt, "What does that mean?", "I mean the term")
    assert attempt["messages"][0]["content"] == "A different question"


@pytest.mark.parametrize("choice,typed", [(True, False), (False, True)])
def test_clarification_route_saves_one_student_bubble(monkeypatch, choice, typed):
    original = "What does sprint goal mean?"
    clarification = "In this assignment" if choice else "I mean the term in this assignment"
    attempt = {
        "status": "in_progress", "processed_requests": [],
        "messages": [{"role": "assistant", "content": "Let's discuss Scrum."},
                     {"role": "user", "content": original}],
        "engine_state": {"socratic": {"pending_clarification": {
            "inline": True, "original_question": original,
            "options": [{"label": "In this assignment", "resolved_message": "Explain the term here."}],
        }}},
    }

    @contextmanager
    def locked(*_args):
        yield None, attempt

    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes.store, "save_attempt", lambda *_args: None)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args: {"tool": "socratic"})
    monkeypatch.setattr(routes.engines, "message", lambda *_args, **_kwargs: {
        "reply": "Here is what the document says.", "socratic": {"phase": "teaching"},
    })
    body = routes.MessageInput(
        request_id=uuid4(), message=clarification,
        clarification_index=0 if choice else None, clarification_text=typed,
    )

    result = routes.message(uuid4(), body, {"user_id": uuid4()})

    student_messages = [item for item in result["messages"] if item["role"] == "user"]
    assert student_messages == [{"role": "user", "content": f"{original}\n\nClarification: {clarification}"}]
    assert result["messages"][-1]["role"] == "assistant"
