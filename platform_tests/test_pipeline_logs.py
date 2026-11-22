from copy import deepcopy
from uuid import uuid4

from platform_app import pipeline_logs, store


def seed_trace(roster):
    assignment_id, attempt_id = uuid4(), uuid4()
    with store.connection() as conn:
        conn.execute('''INSERT INTO assignments_platform
            (id, course_id, creator_id, tool, title, audience, config)
            VALUES (%s,%s,%s,'socratic','Scrum values','course','{}')''',
            (assignment_id, roster['course'], roster['prof']))
        conn.execute('''INSERT INTO assignment_attempts_platform (id,assignment_id,student_id)
            VALUES (%s,%s,%s)''', (attempt_id, assignment_id, roster['student']))
    return assignment_id, {
        'trace_id': uuid4().hex, 'conversation_id': str(attempt_id),
        'started_at': '2026-11-22T12:00:00Z',
        'events': [
            {'stage': 1, 'event': 'assignment_chat_received', 'elapsed_ms': 0,
             'fields': {'step_index': 2, 'message_chars': 50}},
            {'stage': 7, 'event': 'step_readiness_completed', 'elapsed_ms': 1200,
             'fields': {'ready': True, 'model': 'gpt-6-luna', 'provider': 'OpenAI',
                        'student_answer': 'PRIVATE ANSWER', 'retrieval_query': 'PRIVATE QUERY',
                        'api_key': 'sk-very-private-key', 'preview': 'PRIVATE PREVIEW', 'path': '/private/file'}},
        ],
    }


def test_logs_require_signin_and_instructor_access(client, roster):
    assert client.get('/api/platform/pipeline-logs').status_code == 401
    response = client.get('/api/platform/pipeline-logs', headers=roster['headers']['student'])
    assert response.status_code == 403


def test_only_approved_course_instructors_see_assignment_traces(client, roster, monkeypatch):
    assignment, trace = seed_trace(roster)
    monkeypatch.setattr(pipeline_logs, 'recent_traces', lambda *_: [trace])
    response = client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof'])
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    item = response.json()['traces'][0]
    assert item['assignment_id'] == str(assignment)
    assert item['step_index'] == 2
    assert item['status'] == 'complete'
    assert item['events'][1]['fields']['ready'] is True
    assert item['events'][1]['fields']['model'] == 'gpt-6-luna'
    assert 'PRIVATE' not in response.text and 'sk-very-private' not in response.text
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['other_prof']).json()['traces'] == []
    assert client.get(f'/api/platform/pipeline-logs?assignment_id={uuid4()}', headers=roster['headers']['prof']).json()['traces'] == []
    with store.connection() as conn:
        conn.execute("UPDATE course_memberships_platform SET status='pending' WHERE course_id=%s AND user_id=%s",
                     (roster['course'], roster['prof']))
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof']).json()['traces'] == []


def test_in_progress_trace_updates_with_safe_failure_diagnostics(client, roster, monkeypatch):
    _, trace = seed_trace(roster)
    live = deepcopy(trace)
    live['events'] = live['events'][:1]
    monkeypatch.setattr(pipeline_logs, 'recent_traces', lambda *_: [live])
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof']).json()['traces'][0]['status'] == 'in_progress'
    live['events'].append({'stage': 6, 'event': 'qualitative_feedback_failed', 'elapsed_ms': 500,
                          'fields': {'error_type': 'AuthenticationError', 'status_code': 401,
                                     'provider_error_code': 'invalid_api_key', 'fallback': 'no_feedback',
                                     'provider_message': 'PRIVATE PROVIDER TEXT'}})
    item = client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof']).json()['traces'][0]
    assert item['status'] == 'attention'
    assert item['events'][-1]['fields']['status_code'] == 401
    assert 'PRIVATE' not in str(item)


def test_log_failure_is_not_reported_as_empty_success(client, roster, monkeypatch):
    def unavailable(*_):
        raise RuntimeError('database credential must not be returned')
    monkeypatch.setattr(pipeline_logs, 'recent_traces', unavailable)
    response = client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof'])
    assert response.status_code == 503
    assert 'credential' not in response.text


def test_unlinked_public_and_malformed_traces_are_not_exposed(client, roster, monkeypatch):
    _, trace = seed_trace(roster)
    public = {**trace, 'conversation_id': str(uuid4())}
    malformed = {**trace, 'conversation_id': 'not-an-assignment-attempt'}
    monkeypatch.setattr(pipeline_logs, 'recent_traces', lambda *_: [public, malformed])
    response = client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof'])
    assert response.json()['traces'] == []
