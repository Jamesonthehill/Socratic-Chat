from contextlib import contextmanager
from uuid import uuid4

import pytest
from platform_app import routes


@pytest.mark.parametrize("allowed", [True, False, None])
def test_consent_choice_does_not_block_submission(monkeypatch, allowed):
    attempt = {"status": "in_progress", "engine_state": {"socratic": {"phase": "ready_to_submit"}}}
    @contextmanager
    def locked(*args):
        yield object(), attempt
    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes, "get_assignment", lambda *args: {"tool": "socratic"})
    monkeypatch.setattr(routes.engines, "complete", lambda *args: {"completed": True})
    monkeypatch.setattr(routes.store, "save_attempt", lambda *args: None)
    body = routes.CompletionInput(improvement_consent=allowed) if allowed is not None else None
    result = routes.complete(uuid4(), body, {"user_id": uuid4()})
    assert result["status"] == "completed"
    consent = result["engine_state"]["improvement_consent"]
    assert consent["allowed"] is (allowed is True)
    assert consent["notice_version"] == "braintutor-improvement-v1"
    assert consent["recorded_at"]
