"""A student can explore a term and return to the tutor question they paused."""

import asyncio
from contextlib import contextmanager
from uuid import uuid4

from app.classifier import _classification_from_observation
from app.schemas import Source
from platform_app import engines, routes


def test_definition_question_saves_the_current_tutor_question(monkeypatch):
    source = Source(document_id="pdf", chunk_id="pdf:1", title="Python notes",
                    text="A dictionary key identifies a value.", score=1.0)
    step = {"title": "Read the data", "goal": "Use dictionary values",
            "scenario": "A program reads a sandwich order.",
            "question": "How would you read the selected size?"}
    assignment = {"id": uuid4(), "tool": "socratic", "title": "Python",
                  "snapshot": {"config": {"learning_steps": [step]}, "chunks": []}}
    attempt = {"id": uuid4(), "messages": [{"role": "assistant", "content": step["question"],
                                               "next_thinking_step": step["question"]}],
               "engine_state": {"socratic": {"phase": "teaching", "learning_topic": "Read the data",
                                              "learning_step_index": 0,
                                              "next_thinking_step": step["question"]}}}
    calls = []

    async def classify(*_args, **_kwargs):
        return _classification_from_observation(message_role="learning_question",
                                                 concepts=("dictionary key",), subtopic_request=True)

    async def no_term(*_args, **_kwargs):
        return None

    async def answer(*_args, **kwargs):
        calls.append(kwargs)
        return "A key names a value. In the order dictionary, 'size' is a key.\n\nWhich key would read the size?"

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_term)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [source])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)

    result = asyncio.run(engines._socratic_message(assignment, attempt, "What is a dictionary key?"))
    detour = result["socratic"]["learning_detour"]
    assert detour["question"] == step["question"]
    assert detour["step_index"] == 0
    assert calls[0]["learning_detour"] == detour
    assert result["socratic"]["next_thinking_step"] == "Which key would read the size?"


def test_return_action_restores_question_without_a_model_call(monkeypatch):
    assignment_id = uuid4()
    original = "How would you read the selected size?"
    attempt = {"status": "active", "messages": [], "engine_state": {"socratic": {
        "phase": "teaching", "learning_step_index": 0,
        "learning_topic": "dictionary key", "next_thinking_step": "Which key would read the size?",
        "learning_detour": {"question": original, "learning_topic": "Read the data",
                            "step_index": 0, "stable_concept": "dictionary", "active_concept": "dictionary"},
    }}}

    @contextmanager
    def locked_attempt(*_args):
        yield object(), attempt

    monkeypatch.setattr(routes.store, "locked_attempt", locked_attempt)
    monkeypatch.setattr(routes.store, "save_attempt", lambda *_args: None)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args: {"tool": "socratic"})
    monkeypatch.setattr(routes, "public_attempt", lambda value: value)

    result = routes.resume_socratic_question(assignment_id, account={"user_id": uuid4()})
    state = result["engine_state"]["socratic"]
    assert "learning_detour" not in state
    assert state["learning_topic"] == "Read the data"
    assert state["next_thinking_step"] == original
    assert result["messages"][-1]["next_thinking_step"] == original
