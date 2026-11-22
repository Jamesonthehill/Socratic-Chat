"""Canvas deletion must target the linked assignment and preserve local state on failure."""
from contextlib import contextmanager
from pathlib import Path
import sys
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Socratic-Chat/backend"))

from platform_app import canvas_lms, routes
from platform_app.schemas import CanvasDeleteRequest


def test_canvas_delete_uses_exact_endpoint_and_bearer_header():
    seen = []

    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={"id": 42})

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        canvas_lms.delete_assignment(7, 42, "teacher-token", client=client)
    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/api/v1/courses/7/assignments/42"
    assert seen[0].headers["Authorization"] == "Bearer teacher-token"
    assert "teacher-token" not in str(seen[0].url)


class FakeConnection:
    def __init__(self):
        self.updated = False

    def execute(self, query, parameters):
        if "SELECT canvas_course_id, canvas_assignment_id" in query:
            return self
        if "UPDATE assignments_platform" in query:
            self.updated = True
        return self

    def fetchone(self):
        return {"canvas_course_id": 7, "canvas_assignment_id": 42}


def test_canvas_failure_does_not_archive(monkeypatch):
    conn = FakeConnection()

    @contextmanager
    def connection():
        yield conn

    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: {"status": "published"})
    monkeypatch.setattr(canvas_lms, "get_assignment", lambda *_args: {"id": "42"})

    def refused(*_args):
        raise canvas_lms.CanvasAPIError(403, "Canvas denied deletion")

    monkeypatch.setattr(canvas_lms, "delete_assignment", refused)
    with pytest.raises(HTTPException) as caught:
        routes.delete_in_canvas(uuid4(), CanvasDeleteRequest(access_token="teacher-token"), account={})
    assert caught.value.status_code == 403
    assert conn.updated is False


def test_canvas_course_mismatch_never_calls_canvas(monkeypatch):
    conn = FakeConnection()

    @contextmanager
    def connection():
        yield conn

    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: {"status": "published"})
    monkeypatch.setattr(canvas_lms, "get_assignment", lambda *_args: pytest.fail("Canvas should not be called"))
    with pytest.raises(HTTPException) as caught:
        routes.delete_in_canvas(uuid4(), CanvasDeleteRequest(access_token="teacher-token", course_id=8), account={})
    assert caught.value.status_code == 422
    assert conn.updated is False


def test_canvas_success_archives_after_remote_delete(monkeypatch):
    conn = FakeConnection()
    events = []

    @contextmanager
    def connection():
        yield conn

    original_execute = conn.execute

    def execute(query, parameters):
        if "UPDATE assignments_platform" in query:
            events.append("archive")
        return original_execute(query, parameters)

    conn.execute = execute
    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *_args, **_kwargs: {"status": "published"})
    monkeypatch.setattr(canvas_lms, "get_assignment", lambda *_args: {"id": "42", "course_id": "7"})
    monkeypatch.setattr(canvas_lms, "delete_assignment", lambda *_args: events.append("delete"))
    result = routes.delete_in_canvas(uuid4(), CanvasDeleteRequest(access_token="teacher-token"), account={})
    assert result == {"status": "archived", "canvas_deleted": True}
    assert events == ["delete", "archive"]
    assert conn.updated is True
