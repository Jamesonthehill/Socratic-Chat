from contextlib import contextmanager
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import Request, Response
from openai import BadRequestError

from platform_app import routes, socratic_setup, step_check
from platform_app.schemas import SocraticLearningStep


def _check(name):
    return {
        "scenario": f"A customer orders in the {name} situation.",
        "question": "Which action is incorrect here?",
        "options": ["Check supplies first", "Take coins despite missing supplies", "Explain the shortage"],
        "incorrect_option_index": 1,
        "expected_reason": "The machine should not take coins when it cannot make the order.",
    }


def test_step_question_count_includes_opening_and_ignores_repeated_questions():
    messages = [
        {"role": "assistant", "next_thinking_step": "What should happen first?"},
        {"role": "user", "content": "Check the supplies."},
        {"role": "assistant", "next_thinking_step": "What should happen first?"},
        {"role": "assistant", "next_thinking_step": "Why check before taking coins?"},
    ]
    assert routes.step_question_count(messages, 1) == 2
    assert routes.step_question_count(messages, 4) == 1


def test_step_check_endpoint_enforces_instructor_question_minimum(monkeypatch):
    assignment_id = uuid4()
    assignment = {"tool": "socratic", "status": "published", "snapshot": {"config": {
        "minimum_step_questions": 2,
        "learning_steps": [{"title": "Check supplies", "checks": [_check("first"), _check("second")]}],
    }}}
    attempt = {"status": "in_progress", "messages": [
        {"role": "assistant", "next_thinking_step": "What comes first?"},
        {"role": "user", "content": "Check ingredients."},
    ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
        "step_started_at_message_count": 1}}, "processed_requests": []}
    @contextmanager
    def locked(*_args):
        yield None, attempt
    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args: assignment)
    account = {"user_id": uuid4()}
    body = routes.SocraticStepCheckInput(request_id=uuid4(), action="submit", option_index=0,
                                         reason="This would skip the inventory check.")
    with pytest.raises(HTTPException, match="2 tutor question"):
        routes.socratic_step_check(assignment_id, body, account)
    attempt["messages"].append({"role": "assistant", "next_thinking_step": "What comes first?"})
    with pytest.raises(HTTPException, match="2 tutor question"):
        routes.socratic_step_check(assignment_id, body, account)
    attempt["messages"].append({"role": "assistant", "next_thinking_step": "Why before coins?"})
    monkeypatch.setattr(routes.store, "save_attempt", lambda *_args: None)
    result = routes.socratic_step_check(assignment_id, body, account)
    assert result["engine_state"]["socratic"]["step_check"]["attempts"] == 1


def test_step_check_schema_requires_two_valid_examples():
    step = SocraticLearningStep.model_validate({
        "title": "Check supplies", "goal": "Explain the inventory check before payment.",
        "evidence_quote": "Check supplies before asking the customer for money.",
        "source_chunk_id": "chunk-1", "checks": [_check("first"), _check("second")],
    })
    assert len(step.checks) == 2
    with pytest.raises(ValueError):
        SocraticLearningStep.model_validate({**step.model_dump(), "checks": [_check("first")]})


def test_generated_checks_survive_source_validation_and_require_another_example():
    step = {
        "title": "Check supplies", "goal": "Explain why supplies are checked before payment.",
        "scenario": "A customer asks for a sandwich and the machine checks its supplies.",
        "question": "What should the machine check before payment?",
        "evidence_quote": "Check supplies before asking the customer for money.",
        "source_chunk_id": "chunk-1", "checks": [_check("first"), _check("second")],
    }
    draft = {"opening_prompt": "What should the machine check first?",
             "student_instructions": "You will reason about the machine's order flow.",
             "minimum_messages": 2, "source_chunk_ids": ["chunk-1"],
             "learning_steps": [step, {**step, "title": "Explain the result"}]}
    evidence = '[chunk_id=chunk-1] Check supplies before asking the customer for money.'
    result = socratic_setup.validate_draft(json.dumps(draft), {"chunk-1"}, evidence)
    assert len(result["learning_steps"][0]["checks"]) == 2
    draft["learning_steps"][0]["checks"][1]["scenario"] = draft["learning_steps"][0]["checks"][0]["scenario"]
    with pytest.raises(ValueError, match="different example"):
        socratic_setup.validate_draft(json.dumps(draft), {"chunk-1"}, evidence)


def test_first_failed_reason_does_not_reveal_instructor_answer(monkeypatch):
    async def complete(*_args):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "sufficient": False,
            "feedback": "The full answer is that payment must come after checking supplies.",
        })))])
    monkeypatch.setattr(step_check.settings, "llm_client_config", lambda *_args: ("Ollama", "key", "url", "model"))
    monkeypatch.setattr(step_check, "chat_completion", complete)
    sufficient, feedback = asyncio.run(step_check.assess_reason(_check("first"), "Take coins anyway", "Because it is wrong."))
    assert not sufficient
    assert "payment must" not in feedback


def test_checks_are_drafted_in_a_small_separate_request(monkeypatch):
    calls = []
    checks = [_check("first"), _check("second")]
    async def complete(_key, _url, request):
        calls.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"checks": checks})))])
    monkeypatch.setattr(socratic_setup, "chat_completion", complete)
    result = asyncio.run(socratic_setup.generate_checks_for_step({
        "title": "Check supplies", "goal": "Explain why the machine checks supplies before payment.",
        "scenario": "A customer selects a sandwich.", "question": "What should happen first?",
    }, "Check supplies before taking coins.", "Ollama", "key", "url", "model"))
    assert len(result) == 2
    assert calls[0]["reasoning_effort"] == "none"
    assert calls[0]["max_tokens"] == 1600
    assert "step_scene" in calls[0]["messages"][1]["content"]


def test_groq_schema_rejection_recovers_trailing_empty_quiz_options(monkeypatch):
    checks = [_check("first"), _check("second")]
    for check in checks:
        check["options"] = [*check["options"], "Valid fourth option", ""]
    raw = json.dumps({"checks": checks})
    response = Response(400, request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    error = BadRequestError("Generated JSON does not match the expected schema", response=response,
                            body={"error": {"code": "json_validate_failed", "failed_generation": raw}})
    calls = []

    async def complete(_key, _url, request):
        calls.append(request)
        raise error

    monkeypatch.setattr(socratic_setup, "chat_completion", complete)
    result = asyncio.run(socratic_setup.generate_checks_for_step({
        "title": "Check supplies", "goal": "Explain why supplies are checked before payment.",
        "scenario": "A customer selects a sandwich.", "question": "What should happen first?",
    }, "Check supplies before taking coins.", "Groq", "key", "url", "openai/gpt-oss-20b"))
    assert len(calls) == 1
    assert len(result) == 2
    assert all(len(check["options"]) == 4 for check in result)


def test_schema_rejection_with_real_fifth_option_retries_instead_of_dropping_it(monkeypatch):
    checks = [_check("first"), _check("second")]
    checks[0]["options"] = [*checks[0]["options"], "Fourth choice", "Fifth choice"]
    raw = json.dumps({"checks": checks})
    response = Response(400, request=Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    error = BadRequestError("Generated JSON does not match the expected schema", response=response,
                            body={"error": {"code": "json_validate_failed", "failed_generation": raw}})
    calls = []

    async def complete(_key, _url, request):
        calls.append(request)
        if len(calls) == 1:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "checks": [_check("first"), _check("second")],
        })))])

    monkeypatch.setattr(socratic_setup, "chat_completion", complete)
    result = asyncio.run(socratic_setup.generate_checks_for_step({
        "title": "Check supplies", "goal": "Explain why supplies are checked before payment.",
        "scenario": "A customer selects a sandwich.", "question": "What should happen first?",
    }, "Check supplies before taking coins.", "Groq", "key", "url", "openai/gpt-oss-20b"))
    assert len(calls) == 2
    assert "blank fifth option" in calls[1]["messages"][-1]["content"]
    assert len(result) == 2


def test_student_config_hides_answer_key_and_expected_reason():
    checks = [_check("first"), _check("second")]
    assignment = {
        "tool": "socratic", "status": "published", "config": {},
        "snapshot": {"config": {"minimum_messages": 1, "learning_steps": [{
            "title": "Check supplies", "goal": "Check before payment", "checks": checks,
            "source_chunk_id": "chunk-1",
        }]}, "chunks": []},
    }
    public = routes.public_assignment(assignment)["student_config"]["learning_steps"][0]["checks"]
    assert public[0] == step_check.public_check(checks[0])
    assert "incorrect_option_index" not in str(public)
    assert "expected_reason" not in str(public)


def test_published_checks_can_be_reviewed_and_saved_without_changing_steps(monkeypatch):
    from platform_app.routes import PublishedStepChecksInput
    assignment_id = uuid4()
    step = {"title": "Check supplies", "goal": "Check available ingredients before payment.",
            "scenario": "A customer chooses a sandwich.", "question": "What happens first?",
            "source_chunk_id": "chunk-1"}
    item = {"id": assignment_id, "tool": "socratic", "status": "published",
            "config": {"learning_steps": [step]}, "snapshot": {"config": {
                "learning_steps": [step], "document_ids": ["document-1"], "minimum_messages": 1},
                "chunks": [{"chunk_id": "chunk-1", "document_id": "document-1",
                            "text": "Check ingredients before taking coins."}]}}
    written = {}
    class Result:
        def fetchone(self):
            return {**item, "config": written["config"], "snapshot": written["snapshot"]}
    class Connection:
        def execute(self, _query, params):
            written["config"] = params[0].obj
            written["snapshot"] = params[1].obj
            return Result()
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: item)
    body = PublishedStepChecksInput.model_validate({"checks": [[_check("first"), _check("second")]],
                                                     "minimum_step_questions": 3})
    result = routes.save_published_step_checks(assignment_id, body, account={"authority_level": 1})
    assert result["config"]["learning_steps"][0]["title"] == "Check supplies"
    assert len(written["snapshot"]["config"]["learning_steps"][0]["checks"]) == 2
    assert len(written["config"]["learning_steps"][0]["checks"]) == 2
    assert written["snapshot"]["config"]["minimum_step_questions"] == 3


def test_legacy_published_assignment_can_draft_checks_from_its_cited_source(monkeypatch):
    assignment_id = uuid4()
    step = {"title": "Check supplies", "goal": "Check available ingredients before payment.",
            "scenario": "A customer chooses a sandwich.", "question": "What happens first?",
            "source_chunk_id": "chunk-1"}
    item = {"tool": "socratic", "status": "published", "config": {"learning_steps": [step]},
            "snapshot": {"config": {"learning_steps": [step], "document_ids": ["document-1"]},
                "chunks": [{"chunk_id": "chunk-1", "document_id": "document-1",
                            "text": "Check ingredients before taking coins."}]}}
    @contextmanager
    def connection():
        yield object()
    captured = {}
    async def generate(_step, passage, *_args):
        captured["passage"] = passage
        return [_check("first"), _check("second")]
    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: item)
    monkeypatch.setattr(routes.settings, "llm_client_config", lambda *_args: ("Ollama", "key", "url", "model"))
    monkeypatch.setattr(socratic_setup, "generate_checks_for_step", generate)
    result = asyncio.run(routes.draft_published_step_checks(assignment_id, account={"authority_level": 1}))
    assert captured["passage"] == "Check ingredients before taking coins."
    assert len(result["steps"][0]["checks"]) == 2


def test_published_socratic_settings_preserve_sources_and_existing_checks(monkeypatch):
    assignment_id = uuid4()
    step = {"title": "Check supplies", "goal": "Check ingredients before payment.",
            "scenario": "A customer orders a sandwich.", "question": "What should happen first?",
            "evidence_quote": "Check the bread before taking payment.", "source_chunk_id": "chunk-1",
            "checks": [_check("first"), _check("second")]}
    item = {"id": assignment_id, "tool": "socratic", "status": "published", "instructions": "Old instructions",
            "config": {"learning_steps": [step], "document_ids": ["doc-1"]},
            "snapshot": {"config": {"learning_steps": [step], "document_ids": ["doc-1"]},
                         "chunks": [{"chunk_id": "chunk-1", "document_id": "doc-1", "text": step["evidence_quote"]}]}}
    written = {}
    class Result:
        def fetchone(self):
            return {**item, "instructions": written["instructions"], "config": written["config"],
                    "snapshot": written["snapshot"]}
    class Connection:
        def execute(self, _query, params):
            written.update(instructions=params[0], config=params[1].obj, snapshot=params[2].obj)
            return Result()
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: item)
    body = routes.PublishedSocraticSettingsInput(
        instructions="New instructions", prompt="What would you check?",
        minimum_step_questions=3, learning_steps=[routes.PublishedStepSettings(
            title="Check supplies", goal="Explain the inventory check before payment.",
            scenario="A customer orders a small sandwich.", question="Which ingredients must be checked?",
        )],
    )
    result = routes.update_published_socratic_settings(assignment_id, body, account={"authority_level": 1})
    saved = written["snapshot"]["config"]
    assert result["instructions"] == "New instructions"
    assert saved["minimum_step_questions"] == 3
    assert "minimum_messages" not in saved
    assert saved["learning_steps"][0]["source_chunk_id"] == "chunk-1"
    assert saved["learning_steps"][0]["checks"] == step["checks"]
    assert written["snapshot"]["chunks"] == item["snapshot"]["chunks"]


def test_two_unsuccessful_checks_offer_retry_or_continue_then_record_support(monkeypatch):
    assignment_id = uuid4()
    checks = [_check("first"), _check("second")]
    assignment = {"tool": "socratic", "status": "published", "snapshot": {"config": {
        "learning_steps": [{"title": "Check supplies", "checks": checks}, {"title": "Payment"}],
    }}}
    attempt = {
        "status": "in_progress", "messages": [
            {"role": "assistant", "content": "What comes first?"},
            {"role": "user", "content": "Check the ingredients."},
        ],
        "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
                                     "step_started_at_message_count": 1}},
        "processed_requests": [],
    }

    @contextmanager
    def locked(*_args):
        yield None, attempt

    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args: assignment)
    monkeypatch.setattr(routes.store, "save_attempt", lambda *_args: None)
    account = {"user_id": uuid4()}

    for _ in range(2):
        result = routes.socratic_step_check(assignment_id, routes.SocraticStepCheckInput(
            request_id=uuid4(), action="submit", option_index=0, reason="I think this is wrong because supplies matter."), account)
    progress = result["engine_state"]["socratic"]["step_check"]
    assert progress["status"] == "choice"
    assert "Take coins despite missing supplies" in progress["feedback"]
    with pytest.raises(HTTPException) as error:
        routes.next_socratic_step(assignment_id, account)
    assert error.value.status_code == 409

    result = routes.socratic_step_check(assignment_id, routes.SocraticStepCheckInput(
        request_id=uuid4(), action="try_another"), account)
    assert result["engine_state"]["socratic"]["step_check"]["variant"] == 1
    monkeypatch.setattr(step_check, "assess_reason_sync", lambda *_args: (True, "That explains the problem."))
    result = routes.socratic_step_check(assignment_id, routes.SocraticStepCheckInput(
        request_id=uuid4(), action="submit", option_index=1,
        reason="The machine cannot make the sandwich, so it should not take payment."), account)
    assert result["engine_state"]["socratic"]["step_check"]["status"] == "passed"


def test_continue_with_support_is_recorded_and_advances_without_mastery(monkeypatch):
    assignment_id = uuid4()
    assignment = {"tool": "socratic", "status": "published", "snapshot": {"config": {
        "learning_steps": [{"title": "Check supplies", "checks": [_check("first"), _check("second")]},
                           {"title": "Payment", "goal": "Check the inserted coins."}],
    }, "chunks": []}}
    attempt = {"status": "in_progress", "messages": [
        {"role": "assistant", "content": "What comes first?"},
        {"role": "user", "content": "Check ingredients."},
    ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
        "step_started_at_message_count": 1, "step_check": {
            "step_index": 0, "variant": 0, "attempts": 2, "status": "choice",
        }}}, "processed_requests": []}

    @contextmanager
    def locked(*_args):
        yield None, attempt

    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args: assignment)
    monkeypatch.setattr(routes.store, "save_attempt", lambda *_args: None)
    account = {"user_id": uuid4()}
    result = routes.socratic_step_check(assignment_id, routes.SocraticStepCheckInput(
        request_id=uuid4(), action="continue_with_support"), account)
    assert result["engine_state"]["socratic"]["step_check_results"] == [
        {"step_index": 0, "status": "continued_with_support"}]
    advanced = routes.next_socratic_step(assignment_id, account)
    assert advanced["engine_state"]["socratic"]["learning_step_index"] == 1
