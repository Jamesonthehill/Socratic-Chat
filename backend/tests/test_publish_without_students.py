from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException

from platform_app import routes
from platform_app.schemas import AssignmentInput


@pytest.mark.parametrize("audience", ["course", "selected"])
def test_draft_can_have_no_student_recipients(audience):
    assignment = AssignmentInput(
        course_id=uuid4(),
        tool="socratic",
        title="Discuss the reading",
        audience=audience,
        recipient_ids=[],
    )
    assert assignment.recipient_ids == []


@pytest.mark.parametrize("audience", ["course", "selected"])
def test_publish_succeeds_without_enrolled_students(monkeypatch, audience):
    assignment_id = uuid4()
    course_id = uuid4()
    item = {
        "id": assignment_id,
        "course_id": course_id,
        "audience": audience,
        "status": "draft",
        "config": {},
    }
    statements = []

    class Result:
        def fetchone(self):
            return item if statements[-1].startswith("UPDATE assignments_platform") else None

    class Connection:
        def execute(self, statement, params):
            statements.append(statement)
            return Result()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(routes.store, "connection", connection)
    monkeypatch.setattr(routes, "get_assignment", lambda *args, **kwargs: item)
    monkeypatch.setattr(routes.engines, "publish_snapshot", lambda _: {"config": {}})

    result = routes.publish(assignment_id, {"user_id": uuid4()})

    assert result["id"] == assignment_id
    assert any(sql.startswith("UPDATE assignments_platform") for sql in statements)
    assert not any("count(*)" in sql.lower() for sql in statements)


def test_course_wide_assignment_checks_current_enrollment():
    assignment_id = uuid4()
    course_id = uuid4()
    student_id = uuid4()
    item = {"id": assignment_id, "course_id": course_id, "audience": "course", "status": "published"}
    queries = []

    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

    class Connection:
        def execute(self, statement, params):
            queries.append((statement, params))
            return Result(item if statement.startswith("SELECT * FROM assignments_platform") else {"?column?": 1})

    result = routes.get_assignment(Connection(), assignment_id, {"user_id": student_id})

    assert result == item
    assert "course_memberships_platform" in queries[1][0]
    assert queries[1][1] == (course_id, student_id, assignment_id, "course")


def test_unenrolled_student_still_cannot_open_assignment():
    assignment_id = uuid4()
    item = {"course_id": uuid4(), "audience": "course", "status": "published"}

    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

    class Connection:
        def execute(self, statement, params):
            return Result(item if statement.startswith("SELECT * FROM assignments_platform") else None)

    with pytest.raises(HTTPException) as error:
        routes.get_assignment(Connection(), assignment_id, {"user_id": uuid4()})
    assert error.value.status_code == 404
