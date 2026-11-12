from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from platform_app import routes


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("status", ["in_progress", "completed"])
def test_refresh_preserves_transcript_and_keeps_previous_feedback_on_failure(monkeypatch, fails, status):
    attempt = {"status": status, "result": {"message_count": 1}, "processed_requests": [], "messages": [{"role": "user", "content": "My answer"}],
               "engine_state": {"socratic": {"phase": "ready_to_submit", "completion_summary": {"final_comment": "Old"}}}}
    original = deepcopy(attempt)
    @contextmanager
    def locked(*args):
        yield object(), attempt
    def reflect(assignment, target, reflection):
        assert "completion_summary" not in target["engine_state"]["socratic"]
        if fails:
            raise RuntimeError("offline")
        return {"socratic": {"phase": "ready_to_submit", "completion_summary": {"final_comment": "Updated", "step_reviews": []}}}
    monkeypatch.setattr(routes.store, "locked_attempt", locked)
    monkeypatch.setattr(routes, "get_assignment", lambda *args: {"tool": "socratic", "snapshot": {"config": {}}})
    monkeypatch.setattr(routes.engines, "reflect", reflect)
    monkeypatch.setattr(routes.store, "save_attempt", lambda *args: None)
    body = routes.SocraticReflectionInput(summary="My summary", request_id=uuid4(), regenerate_feedback=True)
    if fails:
        with pytest.raises(HTTPException) as error:
            routes.socratic_reflection(uuid4(), body, {"user_id": uuid4()})
        assert error.value.status_code == 503
        assert attempt == original
    else:
        result = routes.socratic_reflection(uuid4(), body, {"user_id": uuid4()})
        assert result["messages"] == original["messages"]
        assert result["status"] == status
        assert result["result"]["message_count"] == 1
        if status == "completed":
            assert result["result"]["completion_summary"]["final_comment"] == "Updated"
        assert result["engine_state"]["socratic"]["completion_summary"]["final_comment"] == "Updated"
