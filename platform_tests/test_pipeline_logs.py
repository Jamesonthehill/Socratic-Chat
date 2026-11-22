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


def test_prompt_instructions_are_redacted_and_only_visible_inside_the_instructors_course(client, roster, monkeypatch):
    _, trace = seed_trace(roster)
    trace['events'].extend([
        {'stage': 7, 'event': 'model_prompt', 'elapsed_ms': 20, 'fields': {
            'phase': 'step-readiness', 'prompt_role': 'system',
            'prompt_text': 'Use grounded evidence.\nAsk one question. api_key="private secret" teacher@example.edu',
            'prompt_truncated': False}},
        {'stage': 7, 'event': 'model_prompt', 'elapsed_ms': 21, 'fields': {
            'prompt_role': 'user', 'prompt_text': 'PRIVATE STUDENT INPUT'}},
        {'stage': 7, 'event': 'unrelated_event', 'elapsed_ms': 22, 'fields': {
            'prompt_role': 'system', 'prompt_text': 'UNAPPROVED PROMPT FIELD'}},
    ])
    monkeypatch.setattr(pipeline_logs, 'recent_traces', lambda *_: [trace])
    response = client.get('/api/platform/pipeline-logs', headers=roster['headers']['prof'])
    assert response.status_code == 200
    events = response.json()['traces'][0]['events']
    assert events[2]['prompt']['text'].startswith('Use grounded evidence.\nAsk one question.')
    assert '[redacted-secret]' in events[2]['prompt']['text']
    assert '[redacted-email]' in events[2]['prompt']['text']
    assert 'prompt' not in events[3] and 'prompt' not in events[4]
    for value in ('private secret', 'teacher@example.edu', 'PRIVATE STUDENT INPUT', 'UNAPPROVED PROMPT FIELD'):
        assert value not in response.text
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['other_prof']).json()['traces'] == []
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['student']).status_code == 403


def test_instructor_can_generate_prompt_log_without_touching_student_attempts(client, roster, monkeypatch, tmp_path):
    from app import pipeline_logging
    from psycopg.types.json import Jsonb
    assignment_id, _ = seed_trace(roster)
    with store.connection() as conn:
        conn.execute("UPDATE assignments_platform SET status='published', snapshot=%s WHERE id=%s",
                     (Jsonb({'config': {}, 'chunks': []}), assignment_id))
    monkeypatch.setattr(pipeline_logging.settings, 'PIPELINE_TRACE_FILE', tmp_path / 'test-traces.json')
    monkeypatch.setattr(pipeline_logs.engines, 'start', lambda *_: {'messages': [{'role': 'assistant', 'content': 'What would you inspect?'}], 'socratic': {'phase': 'teaching'}})
    def run(assignment, attempt, content, request_id):
        assert attempt['instructor_preview'] is True
        assert 'help understanding' in content
        tokens = pipeline_logging.begin_trace('d' * 32, str(attempt['id']), diagnostic_assignment_id=str(assignment['id']))
        try:
            pipeline_logging.write_llm_request_snapshot('tutor-generation', 'OpenAI', {'model': 'gpt-6-luna',
                'messages': [{'role': 'system', 'content': 'Ask one grounded Socratic question.'}]})
        finally:
            pipeline_logging.end_trace(tokens)
        return {'reply': 'What information would help you decide?'}
    monkeypatch.setattr(pipeline_logs.engines, 'message', run)
    response = client.post('/api/platform/pipeline-logs/test', json={'assignment_id': str(assignment_id)}, headers=roster['headers']['prof'])
    assert response.status_code == 200, response.text
    assert response.json() == {'trace_id': 'd' * 32, 'failed': False}
    result = client.get(f'/api/platform/pipeline-logs?assignment_id={assignment_id}', headers=roster['headers']['prof'])
    trace = next(trace for trace in result.json()['traces'] if trace['trace_id'] == 'd' * 32)
    assert trace['diagnostic'] is True
    assert trace['events'][0]['prompt']['text'] == 'Ask one grounded Socratic question.'
    assert client.get('/api/platform/pipeline-logs', headers=roster['headers']['other_prof']).json()['traces'] == []
    with store.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM assignment_attempts_platform WHERE assignment_id=%s', (assignment_id,)).fetchone()['n'] == 1


def test_diagnostic_requests_require_course_instructor_permission(client, roster, monkeypatch):
    assignment_id, _ = seed_trace(roster)
    def unexpected(*_):
        raise AssertionError('Unauthorized requests must not run the tutor')
    monkeypatch.setattr(pipeline_logs.engines, 'start', unexpected)
    body = {'assignment_id': str(assignment_id)}
    assert client.post('/api/platform/pipeline-logs/test', json=body).status_code == 401
    assert client.post('/api/platform/pipeline-logs/test', json=body, headers=roster['headers']['student']).status_code == 403
    assert client.post('/api/platform/pipeline-logs/test', json=body, headers=roster['headers']['other_prof']).status_code == 403
    assert client.post('/api/platform/pipeline-logs/test', json=body, headers=roster['headers']['prof']).status_code == 409
