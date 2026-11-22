from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from platform_app import engines, store


def seed_assignment(roster, status='published'):
    assignment_id = uuid4()
    config = {'guidance_mode': 'guided', 'document_ids': ['doc1'], 'learning_steps': [{
        'title': 'Inspect feedback', 'goal': 'Explain why evidence guides adaptation.',
        'scenario': 'Students report that registration is too slow.',
        'question': 'What should the team inspect before changing its plan?',
        'source_chunk_id': 'chunk1', 'evidence_quote': 'Inspect progress before adapting the plan.',
    }]}
    snapshot = {'config': config, 'chunks': [{'chunk_id': 'chunk1', 'document_id': 'doc1',
        'title': 'Guide.pdf', 'page_number': 2, 'text': 'Inspect progress before adapting the plan.'}]}
    with store.connection() as conn:
        conn.execute('''INSERT INTO assignments_platform
            (id, course_id, creator_id, tool, title, audience, config, snapshot, status)
            VALUES (%s,%s,%s,'socratic','Registration decisions','course',%s,%s,%s)''',
            (assignment_id, roster['course'], roster['prof'], Jsonb(config), Jsonb(snapshot), status))
    return assignment_id


@pytest.fixture
def preview_assignment(roster):
    created = []
    def create(status='published'):
        assignment_id = seed_assignment(roster, status)
        created.append(assignment_id)
        return assignment_id
    yield create
    with store.connection() as conn:
        for assignment_id in created:
            conn.execute('DELETE FROM assignments_platform WHERE id=%s', (assignment_id,))


def test_preview_reuses_student_configuration_and_opening_without_saving_attempt(client, roster, monkeypatch, preview_assignment):
    assignment_id = preview_assignment()
    monkeypatch.setattr(engines, '_call_socratic_service', lambda *_: None)
    response = client.get(f'/api/platform/assignments/{assignment_id}/student-preview', headers=roster['headers']['prof'])
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()
    assert 'config' not in data['assignment']
    assert data['assignment']['student_config']['learning_steps'][0]['title'] == 'Inspect feedback'
    opening = data['opening']
    assert opening['status'] == 'in_progress'
    assert opening['engine_state']['socratic']['learning_step_index'] == 0
    assert opening['messages'][0]['next_thinking_step'] == 'What should the team inspect before changing its plan?'
    assert opening['messages'][0]['step_source']['page_number'] == 2
    assert 'Students report that registration is too slow.' in opening['messages'][0]['content']
    assert client.get(f'/api/platform/assignments/{assignment_id}/student-preview', headers=roster['headers']['prof']).json()['opening']['id'] == opening['id']
    with store.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM assignment_attempts_platform WHERE assignment_id=%s', (assignment_id,)).fetchone()['n'] == 0


def test_preview_requires_an_approved_instructor_for_the_course(client, roster, preview_assignment):
    assignment_id = preview_assignment()
    path = f'/api/platform/assignments/{assignment_id}/student-preview'
    assert client.get(path).status_code == 401
    assert client.get(path, headers=roster['headers']['student']).status_code == 403
    assert client.get(path, headers=roster['headers']['other_prof']).status_code == 403


def test_unpublished_assignments_cannot_start_preview_engine(client, roster, monkeypatch, preview_assignment):
    assignment_id = preview_assignment(status='draft')
    def unexpected(*_):
        raise AssertionError('Draft previews must not start an engine')
    monkeypatch.setattr(engines, 'start', unexpected)
    assert client.get(f'/api/platform/assignments/{assignment_id}/student-preview', headers=roster['headers']['prof']).status_code == 409
