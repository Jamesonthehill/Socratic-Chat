import asyncio
import json
from types import SimpleNamespace

from app.answer_evaluation import QualitativeFeedback
from app.classifier import _classification_from_observation
from app.schemas import Source
from platform_app import engines, step_check


STEP = {
    "title": "Check ingredients", "goal": "Explain why the machine checks supplies before payment.",
    "scenario": "A customer requests a small sandwich, but the machine has no bread.",
    "question": "What should happen before the machine asks for coins?",
}
SOURCE = Source(document_id="d", chunk_id="c", title="Requirements", score=0.8,
                text="Check ingredients before accepting payment. Reject an order when bread is insufficient.")


def _model_reply(ready, observation):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=json.dumps({"ready": ready, "observation": observation}),
    ))])


def test_readiness_uses_goal_latest_answer_and_evidence(monkeypatch):
    requests = []

    async def complete(_key, _url, request):
        requests.append(request)
        return _model_reply(True, "They explained that taking coins first would charge for an order the machine cannot make")

    monkeypatch.setattr(step_check.settings, "llm_client_config", lambda _role: ("Ollama", "key", "url", "qwen"))
    monkeypatch.setattr(step_check, "chat_completion", complete)
    monkeypatch.setattr(step_check, "write_llm_request_snapshot", lambda *_args: None)
    monkeypatch.setattr(step_check, "update_llm_request_snapshot", lambda *_args, **_kwargs: None)
    ready, observation = asyncio.run(step_check.assess_step_readiness(
        STEP, "The customer should not pay because the sandwich cannot be made without bread.",
        "Why check ingredients first?", [SOURCE],
    ))
    assert ready is True
    assert "charge for an order" in observation
    assert requests[0]["model"] == "qwen"
    assert requests[0]["response_format"]["json_schema"]["name"] == "guided_step_readiness"
    payload = json.loads(requests[0]["messages"][1]["content"])
    assert payload["step_goal"] == STEP["goal"]
    assert payload["course_evidence"] == [SOURCE.text]


def test_readiness_observation_does_not_end_mid_word(monkeypatch):
    async def complete(_key, _url, _request):
        return _model_reply(True, "You explained why the machine checks its ingredients before payment. "
                            + "This shows your reasoning about the order of the transaction " * 5)

    monkeypatch.setattr(step_check.settings, "llm_client_config", lambda _role: ("Ollama", "key", "url", "qwen"))
    monkeypatch.setattr(step_check, "chat_completion", complete)
    monkeypatch.setattr(step_check, "write_llm_request_snapshot", lambda *_args: None)
    monkeypatch.setattr(step_check, "update_llm_request_snapshot", lambda *_args, **_kwargs: None)
    ready, observation = asyncio.run(step_check.assess_step_readiness(
        STEP, "It should check bread before asking for payment.", "Why check ingredients first?", [SOURCE],
    ))
    assert ready is True
    assert observation.endswith("payment.")
    assert "This shows" not in observation


def test_readiness_never_overrides_a_critical_misconception(monkeypatch):
    async def complete(_key, _url, _request):
        return _model_reply(True, "The answer seems relevant")

    monkeypatch.setattr(step_check.settings, "llm_client_config", lambda _role: ("Ollama", "key", "url", "qwen"))
    monkeypatch.setattr(step_check, "chat_completion", complete)
    monkeypatch.setattr(step_check, "write_llm_request_snapshot", lambda *_args: None)
    monkeypatch.setattr(step_check, "update_llm_request_snapshot", lambda *_args, **_kwargs: None)
    feedback = QualitativeFeedback(concept="payment", supported_concepts=(), missing_concepts=("ingredient check",),
                                   critical_misconception=True, misconception="Charge before checking bread.", feedback="Check bread first.")
    assert asyncio.run(step_check.assess_step_readiness(STEP, "Take the money first.", "What happens first?", [SOURCE], feedback)) == (False, "")


def test_repeated_questions_do_not_advance_step_readiness():
    messages = [
        {"role": "assistant", "next_thinking_step": "What happens first?"},
        {"role": "user", "content": "I don't know."},
        {"role": "assistant", "next_thinking_step": "What happens first?"},
    ]
    assert step_check.count_step_questions(messages, 1) == 1


def test_ready_guided_turn_stops_asking_and_invites_step_quiz(monkeypatch):
    from uuid import uuid4

    async def classify(_message, _history, **_kwargs):
        return _classification_from_observation(message_role="student_answer", concepts=("ingredient check",))

    async def no_resolution(*_args, **_kwargs):
        return None

    async def no_feedback(*_args, **_kwargs):
        return None

    async def ready(*_args, **_kwargs):
        return True, "You explained why payment must wait until ingredients are checked."

    async def unexpected_generation(*_args, **_kwargs):
        raise AssertionError("A ready step should stop asking tutor questions.")

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", no_feedback)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [SOURCE])
    monkeypatch.setattr(engines.step_check, "assess_step_readiness", ready)
    monkeypatch.setattr(engines.rag, "generate_answer", unexpected_generation)
    assignment = {"id": uuid4(), "title": "Sandwich machine", "snapshot": {
        "config": {"minimum_step_questions": 2, "learning_steps": [{**STEP, "checks": [{"question": "Which action is incorrect?"}]}]},
        "chunks": [{"document_id": "d", "chunk_id": "c", "text": SOURCE.text}],
    }}
    attempt = {"id": uuid4(), "messages": [
        {"role": "assistant", "content": "What should happen first?", "next_thinking_step": "What should happen first?"},
        {"role": "user", "content": "Check ingredients."},
        {"role": "assistant", "content": "Why before payment?", "next_thinking_step": "Why before payment?"},
    ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
                                      "step_started_at_message_count": 1}}}
    result = asyncio.run(engines._socratic_message(
        assignment, attempt, "The machine should check bread first so it doesn't take money for an order it cannot make.",
    ))
    assert "Finish the conversation and summarize" in result["reply"]
    assert result["socratic"]["next_thinking_step"] == ""
    assert result["socratic"]["step_readiness"]["ready"] is True


def test_claim_check_does_not_count_as_answer_to_previous_step_question(monkeypatch):
    from uuid import uuid4

    feedback = QualitativeFeedback(
        concept="Sprint Backlog", supported_concepts=("Sprint Goal", "plan"),
        missing_concepts=("selected Product Backlog items",),
        critical_misconception=False, misconception="The whole Product Backlog is included.",
        feedback="The Sprint Backlog includes selected items, not the whole Product Backlog.",
    )

    async def classify(_message, _history, **_kwargs):
        return _classification_from_observation(message_role="confirmation_request", concepts=("Sprint Backlog",))

    async def no_resolution(*_args, **_kwargs):
        return None

    async def evaluate(*_args, **_kwargs):
        return feedback

    async def unexpected_readiness(*_args, **_kwargs):
        raise AssertionError("A claim check must not complete the active step.")

    async def answer(_message, _history, _sources, **kwargs):
        assert kwargs["evaluation"] is feedback
        assert kwargs["misconception_context"] is None
        return "Almost: it includes selected Product Backlog items, not the whole list."

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", evaluate)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [SOURCE])
    monkeypatch.setattr(engines.step_check, "assess_step_readiness", unexpected_readiness)
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    assignment = {"id": uuid4(), "title": "Scrum", "snapshot": {
        "config": {"minimum_step_questions": 1, "learning_steps": [{**STEP, "checks": [{"question": "Which action is incorrect?"}]}]},
        "chunks": [{"document_id": "d", "chunk_id": "c", "text": SOURCE.text}],
    }}
    attempt = {"id": uuid4(), "messages": [
        {"role": "assistant", "content": "How would you adjust the Sprint Goal for mobile signup?",
         "next_thinking_step": "How would you adjust the Sprint Goal for mobile signup?"},
    ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
                                      "step_started_at_message_count": 0}}}
    result = asyncio.run(engines._socratic_message(
        assignment, attempt, "So the Sprint Backlog includes the Sprint Goal, Product Backlog, and a plan?",
    ))
    assert "selected Product Backlog items" in result["reply"]
    assert result["socratic"].get("answered_question_count", 0) == 0
    assert "step_readiness" not in result["socratic"]


def test_tutor_scenario_role_question_does_not_require_document_hit(monkeypatch):
    from uuid import uuid4

    async def classify(_message, _history, **_kwargs):
        return _classification_from_observation(message_role="follow_up", concepts=("Maya",))

    async def no_resolution(*_args, **_kwargs):
        return None

    async def no_feedback(*_args, **_kwargs):
        return None

    async def explain_role(_message, _history, sources, **_kwargs):
        assert sources == []
        return "I didn't say who Maya was. I meant the customer in this example."

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", no_feedback)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [])
    monkeypatch.setattr(engines.rag, "generate_answer", explain_role)
    opening = (
        "The machine checks inventory before payment. "
        "What would Maya do if only 1 slice of bread were left?"
    )
    assignment = {"id": uuid4(), "title": "Sandwich machine", "snapshot": {
        "config": {"learning_steps": [{**STEP, "scenario": opening}]},
        "chunks": [{"document_id": "d", "chunk_id": "c", "text": SOURCE.text}],
    }}
    attempt = {"id": uuid4(), "messages": [
        {"role": "assistant", "content": opening},
        *[{"role": "user", "content": "I'm still thinking."} for _ in range(9)],
    ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0}}}

    result = asyncio.run(engines._socratic_message(assignment, attempt, "Maya is customer or developer?"))
    assert "I didn't say who Maya was" in result["reply"]
