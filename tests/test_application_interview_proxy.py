from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from platform_app.main import app as platform_app
from platform_app import routes, shared_rag
from platform_app.schemas import ApplicationInterviewTurn


@pytest.fixture
def gateway(monkeypatch):
    @contextmanager
    def connection():
        yield 'connection'
    monkeypatch.setattr(routes.store, 'connection', connection)
    assignment = Mock(return_value={'tool':'self-directed-learning'})
    monkeypatch.setattr(routes, 'get_assignment', assignment)
    identity = Mock(return_value='trusted-student-id')
    forward = Mock(return_value={'status':'active'})
    report = Mock(return_value=[])
    monkeypatch.setattr(routes, 'self_directed_identity', identity)
    monkeypatch.setattr(routes.engines, 'self_directed_call', forward)
    monkeypatch.setattr(shared_rag, 'pipeline', report)
    return assignment, identity, forward, report


def test_student_proxy_checks_enrollment_and_never_accepts_student_identity(gateway):
    assignment, identity, forward, _ = gateway
    body = ApplicationInterviewTurn(action='start',turn_id='request-1')
    account = {'user_id':'signed-in-account'}
    routes.self_directed_application_interview('assignment-a', body, account)
    assignment.assert_called_once_with('connection','assignment-a',account)
    identity.assert_called_once_with(account)
    forward.assert_called_once_with('trusted-student-id','POST','/api/student/assignments/assignment-a/application-interview',json=body.model_dump())
    with pytest.raises(ValueError):
        ApplicationInterviewTurn(action='start',turn_id='r',student_id='someone-else')


@pytest.mark.parametrize('role', ['student', 'instructor'])
def test_gateway_denies_access_before_contacting_sdl(gateway, role):
    assignment, identity, forward, report = gateway
    assignment.side_effect = HTTPException(403, 'Access revoked')
    with pytest.raises(HTTPException):
        if role == 'student':
            routes.self_directed_application_interview('assignment-a', ApplicationInterviewTurn(action='start',turn_id='r'), {'user_id':'u'})
        else:
            routes.instructor_application_interviews('assignment-a', {'user_id':'u'})
    identity.assert_not_called()
    forward.assert_not_called()
    report.assert_not_called()


def test_instructor_report_checks_course_management(gateway):
    assignment, _, _, report = gateway
    account = {'user_id':'teacher'}
    assert routes.instructor_application_interviews('assignment-a',account) == []
    assignment.assert_called_once_with('connection','assignment-a',account,manage=True)
    report.assert_called_once_with('GET','/internal/platform/lessons/assignment-a/application-interviews')


def test_report_route_requires_instructor_role(gateway):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.user] = lambda: {'user_id':'student','authority_level':2}
    with TestClient(app) as client:
        result = client.get('/api/platform/assignments/assignment-a/application-interviews')
    assert result.status_code == 403
    gateway[3].assert_not_called()
