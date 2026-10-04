from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import settings
from platform_app import canvas_lms, canvas_tokens, engines, store


def test_shared_login_and_public_frontend(client, roster):
    response = client.post('/api/auth/login', json={'identifier': roster['prof'], 'password': 'platform-test-password'})
    assert response.status_code == 200, response.text
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.get('/api/platform/tools', headers=headers).status_code == 200
    assert 'PLATFORM_URL' in client.get('/config.js').text
    assert client.get('/').status_code == 200


def draft(client, roster, tool='socratic', **changes):
    body = dict(course_id=roster['course'], tool=tool, title='Week 3', instructions='Think carefully.', audience='selected',
                recipient_ids=[roster['student']], config={})
    body.update(changes)
    response = client.post('/api/platform/assignments', headers=roster['headers']['prof'], json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def publish(client, roster, assignment, monkeypatch):
    monkeypatch.setattr(engines, 'publish_snapshot', lambda a: {'config': a['config'], 'chunks': [], 'module_id': str(a['id'])})
    res = client.post(f"/api/platform/assignments/{assignment['id']}/publish", headers=roster['headers']['prof'])
    assert res.status_code == 200, res.text


def test_requires_signed_session_and_professor(client, roster):
    assert client.get('/api/platform/assignments').status_code == 401
    assert client.get('/api/platform/assignments', headers={'X-User-Id':roster['prof']}).status_code == 401
    assert client.post('/api/platform/assignments', headers=roster['headers']['student'], json={}).status_code == 403


def test_canvas_import_requires_professor_and_creates_socratic_draft(client, roster, monkeypatch):
    course_calls = []
    monkeypatch.setattr(canvas_lms, 'list_courses', lambda token: course_calls.append(token) or [
        {'id': '77', 'name': 'Software Engineering', 'course_code': 'ITSC 3155'}
    ])
    assignment = {
        'id': '88',
        'name': 'Canvas architecture reflection',
        'description': 'Explain one architecture tradeoff.',
        'due_at': '2026-10-01T16:00:00Z',
        'html_url': 'https://instructure.charlotte.edu/courses/77/assignments/88',
        'points_possible': 10,
    }
    monkeypatch.setattr(canvas_lms, 'get_assignment', lambda course_id, assignment_id, token: assignment)

    credentials = {'access_token': 'canvas-test-token'}
    assert client.post(
        '/api/platform/integrations/canvas/courses',
        headers=roster['headers']['student'],
        json=credentials,
    ).status_code == 403
    courses = client.post(
        '/api/platform/integrations/canvas/courses',
        headers=roster['headers']['prof'],
        json=credentials,
    )
    assert courses.status_code == 200
    assert course_calls == ['canvas-test-token']

    imported = client.post(
        '/api/platform/integrations/canvas/import',
        headers=roster['headers']['prof'],
        json={
            **credentials,
            'course_id': 77,
            'assignment_id': 88,
            'platform_course_id': roster['course'],
            'tool': 'socratic',
        },
    )
    assert imported.status_code == 201, imported.text
    draft = imported.json()
    assert draft['tool'] == 'socratic'
    assert draft['status'] == 'draft'
    assert draft['title'] == assignment['name']
    assert assignment['html_url'] in draft['instructions']
    assert draft['config']['document_ids'] == []

    reflection = client.post(
        '/api/platform/integrations/canvas/import',
        headers=roster['headers']['prof'],
        json={
            **credentials,
            'course_id': 77,
            'assignment_id': 88,
            'platform_course_id': roster['course'],
            'tool': 'reflections',
        },
    )
    assert reflection.status_code == 201, reflection.text
    assert reflection.json()['tool'] == 'reflections'
    assert reflection.json()['config']['module_type'] == 'topic_based'


def test_canvas_connection_is_saved_and_reused_server_side(client, roster, monkeypatch):
    saved = {}
    monkeypatch.setattr(canvas_tokens, 'is_configured', lambda: True)
    monkeypatch.setattr(
        canvas_tokens,
        'save',
        lambda user_id, token: saved.update(user_id=user_id, token=token),
    )
    monkeypatch.setattr(
        canvas_tokens,
        'status',
        lambda user_id: {
            'connected': saved.get('user_id') == user_id,
            'encryption_configured': True,
        },
    )
    monkeypatch.setattr(canvas_tokens, 'load', lambda user_id: saved.get('token'))
    monkeypatch.setattr(canvas_tokens, 'mark_verified', lambda user_id: None)
    monkeypatch.setattr(canvas_tokens, 'delete', lambda user_id: bool(saved.clear() is None))

    calls = []
    monkeypatch.setattr(
        canvas_lms,
        'list_courses',
        lambda token: calls.append(token) or [
            {'id': '77', 'name': 'Software Engineering', 'course_code': 'ITSC 3155'}
        ],
    )

    connected = client.post(
        '/api/platform/integrations/canvas/connection',
        headers=roster['headers']['prof'],
        json={'access_token': 'canvas-test-token'},
    )
    assert connected.status_code == 200, connected.text
    assert connected.json()['connected'] is True
    assert connected.json()['courses'][0]['id'] == '77'
    assert saved['token'] == 'canvas-test-token'

    reused = client.post(
        '/api/platform/integrations/canvas/courses',
        headers=roster['headers']['prof'],
        json={},
    )
    assert reused.status_code == 200, reused.text
    assert calls == ['canvas-test-token', 'canvas-test-token']

    disconnected = client.delete(
        '/api/platform/integrations/canvas/connection',
        headers=roster['headers']['prof'],
    )
    assert disconnected.status_code == 200
    assert disconnected.json()['connected'] is False


def test_canvas_assignment_endpoints_reject_student_only_source_course(client, roster, monkeypatch):
    calls = []

    def learner_enrollments(path, token, **_kwargs):
        calls.append((path, token))
        assert path == 'users/self/enrollments'
        return [{'course_id': 77, 'type': 'StudentEnrollment', 'enrollment_state': 'active'}]

    monkeypatch.setattr(canvas_lms, '_get_pages', learner_enrollments)
    monkeypatch.setattr(canvas_lms, '_get_one', lambda *_args, **_kwargs: pytest.fail('Canvas content must not be fetched'))
    monkeypatch.setattr(canvas_tokens, 'load', lambda _user_id: 'saved-token')

    assignments = client.post(
        '/api/platform/integrations/canvas/assignments',
        headers=roster['headers']['prof'],
        json={'course_id': 77, 'access_token': 'inline-token'},
    )
    assert assignments.status_code == 403

    imported = client.post(
        '/api/platform/integrations/canvas/import',
        headers=roster['headers']['prof'],
        json={
            'course_id': 77,
            'assignment_id': 88,
            'platform_course_id': roster['course'],
            'tool': 'socratic',
        },
    )
    assert imported.status_code == 403
    assert calls == [
        ('users/self/enrollments', 'inline-token'),
        ('users/self/enrollments', 'saved-token'),
    ]
    assert client.get('/api/platform/assignments', headers=roster['headers']['prof']).json() == []


def test_create_canvas_course_checks_live_role_and_server_metadata(client, roster, monkeypatch):
    enrollment_type = {'value': 'StudentEnrollment'}

    def enrollments(path, _token, **_kwargs):
        assert path == 'users/self/enrollments'
        return [{'course_id': 77, 'type': enrollment_type['value'], 'enrollment_state': 'active'}]

    monkeypatch.setattr(canvas_lms, '_get_pages', enrollments)
    monkeypatch.setattr(
        canvas_lms,
        '_get_one',
        lambda path, _token, **_kwargs: {
            'id': 77,
            'name': 'Software Engineering',
            'course_code': 'ITSC 3155',
        },
    )
    request = {'course_id': 77, 'access_token': 'inline-token'}
    path = '/api/platform/integrations/canvas/course'

    assert client.post(path, headers=roster['headers']['student'], json=request).status_code == 403
    assert client.post(path, headers=roster['headers']['prof'], json=request).status_code == 403

    enrollment_type['value'] = 'TeacherEnrollment'
    created = client.post(path, headers=roster['headers']['prof'], json=request)
    assert created.status_code == 201, created.text
    assert created.json()['course_code'] == 'ITSC 3155'
    assert created.json()['title'] == 'Software Engineering'
    assert created.json()['membership_role'] == 'instructor'


def test_canvas_token_migration_and_encrypted_round_trip(database, roster, monkeypatch):
    monkeypatch.setenv('CANVAS_TOKEN_ENCRYPTION_KEY', 'integration-test-secret-' + 'x' * 32)
    canvas_tokens.save(roster['prof'], 'canvas-integration-token')

    assert canvas_tokens.load(roster['prof']) == 'canvas-integration-token'
    assert canvas_tokens.status(roster['prof'])['connected'] is True
    with store.connection() as conn:
        row = conn.execute(
            "SELECT token_ciphertext, current_schema() AS schema_name "
            "FROM canvas_api_connections_platform WHERE user_id=%s",
            (roster['prof'],),
        ).fetchone()
    assert b'canvas-integration-token' not in bytes(row['token_ciphertext'])
    assert row['schema_name'] == settings.PLATFORM_DB_SCHEMA

    assert canvas_tokens.delete(roster['prof']) is True


def test_draft_publish_visibility_and_frozen_config(client, roster, monkeypatch):
    item, body = draft(client, roster)
    sid = item['id']; path = f'/api/platform/assignments/{sid}'
    assert client.get(path, headers=roster['headers']['student']).status_code == 404
    assert client.get(path, headers=roster['headers']['other_prof']).status_code == 403
    publish(client, roster, item, monkeypatch)
    visible = client.get(path, headers=roster['headers']['student'])
    assert visible.status_code == 200
    assert 'config' not in visible.json() and 'snapshot' not in visible.json()
    assert client.get(path, headers=roster['headers']['other_student']).status_code == 404
    assert client.post(path+'/start', headers=roster['headers']['other_student']).status_code == 404
    assert client.put(path, headers=roster['headers']['prof'], json=body).status_code == 409
    duplicate = client.post(path+'/duplicate', headers=roster['headers']['prof']).json()
    assert duplicate['status'] == 'draft' and duplicate['id'] != sid


def test_socratic_snapshot_survives_material_changes(client, roster, monkeypatch):
    monkeypatch.setattr(engines.db, 'list_rag_files', lambda **kw: [{'document_id':'doc'}])
    chunks = [{'document_id':'doc','chunk_id':'doc:0','course_id':roster['course'],'title':'Notes','text':'An actor is an external role.','embedding':[1.0, 0.0]}]
    monkeypatch.setattr(engines.db, 'snapshot_document_chunks', lambda *_: chunks.copy())
    monkeypatch.setattr(engines.db, 'get_course', lambda *_: {'course_code':'SE101','title':'Software Engineering','description':''})
    monkeypatch.setattr(engines.rag, 'create_embeddings', lambda *_: [[1.0, 0.0]])
    async def answer(*_args, **_kwargs):
        return 'An actor is an external role. What system interaction would you expect?'
    monkeypatch.setattr(engines.rag, 'generate_answer', answer)
    item, _ = draft(client, roster, config={'document_ids':['doc'], 'minimum_messages':2})
    path=f"/api/platform/assignments/{item['id']}"; h=roster['headers']['student']
    assert client.post(path+'/publish', headers=roster['headers']['prof']).status_code == 200
    chunks.clear()
    started=client.post(path+'/start',headers=h).json()
    assert client.post(path+'/start',headers=h).json()['id']==started['id']
    assert client.post(path+'/complete',headers=h).status_code==422
    rid=str(uuid4()); message={'message':'What is an actor?', 'request_id':rid}
    res=client.post(path+'/messages',headers=h,json=message)
    assert res.status_code==200,res.text
    assert 'external role' in res.json()['messages'][-1]['content']
    assert client.post(path+'/messages',headers=h,json=message).json()['messages']==res.json()['messages']
    assert client.post(path+'/complete',headers=h).status_code==422
    client.post(path+'/messages',headers=h,json={**message,'request_id':str(uuid4())})
    assert client.post(path+'/complete',headers=h).json()['status']=='completed'
    assert client.post(path+'/complete',headers=h).json()['status']=='completed'
    assert client.get(path+'/attempt',headers=h).json()['status']=='completed'
    assert client.post(path+'/messages',headers=h,json={**message,'request_id':str(uuid4())}).status_code==409


def test_cross_course_documents_rejected(client, roster, monkeypatch):
    monkeypatch.setattr(engines.db, 'list_rag_files', lambda **kw:[{'document_id':'owned'}])
    item,_=draft(client,roster,config={'document_ids':['someone-elses-doc']})
    assert client.post(f"/api/platform/assignments/{item['id']}/publish",headers=roster['headers']['prof']).status_code==422


def test_whole_course_recipients_fixed_at_publish_and_revoke_access(client, roster, monkeypatch):
    item,_=draft(client,roster,audience='course',recipient_ids=[])
    publish(client,roster,item,monkeypatch)
    path=f"/api/platform/assignments/{item['id']}"
    assert client.get(path,headers=roster['headers']['other_student']).status_code==200
    with store.connection() as conn:
        conn.execute("UPDATE course_memberships_platform SET status='rejected' WHERE course_id=%s AND user_id=%s",(roster['course'],roster['student']))
    assert client.get(path,headers=roster['headers']['student']).status_code==404
    assert client.post(path+'/start',headers=roster['headers']['student']).status_code==404


def test_invalid_recipient_rolls_back_draft(client,roster):
    res=client.post('/api/platform/assignments',headers=roster['headers']['prof'],json={'course_id':roster['course'],'tool':'socratic','title':'bad','audience':'selected','recipient_ids':[str(uuid4())]})
    assert res.status_code==422
    assert client.get('/api/platform/assignments',headers=roster['headers']['prof']).json()==[]


def test_failed_publish_does_not_expose_draft(client,roster,monkeypatch):
    item,_=draft(client,roster,tool='reflections',config={'sub_topics':['requirements']})
    def unavailable(a): raise HTTPException(503,'Engine unavailable')
    monkeypatch.setattr(engines,'publish_snapshot',unavailable)
    path=f"/api/platform/assignments/{item['id']}"
    assert client.post(path+'/publish',headers=roster['headers']['prof']).status_code==503
    assert client.get(path,headers=roster['headers']['prof']).json()['status']=='draft'
    assert client.get(path,headers=roster['headers']['student']).status_code==404


@pytest.mark.parametrize('tool', ['reflections','student-agent'])
def test_routes_to_correct_engine_and_resumes(client,roster,monkeypatch,tool):
    topic=engines.topic_templates()[0]
    item,_=draft(client,roster,tool=tool,config={'topic':topic} if tool=='student-agent' else {'sub_topics':['requirements']})
    publish(client,roster,item,monkeypatch)
    calls=[]
    def remote(t,method,path,**kw):
        calls.append((t,path,kw['json']))
        if path.endswith('/start'):
            return {'messages':[{'role':'assistant','content':'Hello'}],'phase':'reading'} if t=='student-agent' else {'greeting':'Hello','total_questions':1}
        return {'messages':[{'role':'assistant','content':'Hello'},{'role':'user','content':'My response'},{'role':'assistant','content':'Continue'}],'phase':'complete'} if t=='student-agent' else {'reply':'Continue','question_index':1,'total_questions':1}
    monkeypatch.setattr(engines,'call',remote)
    path=f"/api/platform/assignments/{item['id']}"; h=roster['headers']['student']
    started=client.post(path+'/start',headers=h)
    assert started.status_code==200,started.text
    assert calls[0][0]==tool and calls[0][2]['session_id']==started.json()['id']
    if tool=='reflections': assert calls[0][2]['student_id']==roster['student']
    response=client.post(path+'/messages',headers=h,json={'message':'My response','request_id':str(uuid4())})
    assert response.status_code==200,response.text
    assert client.get(path+'/attempt',headers=h).json()['messages']==response.json()['messages']
    before=len(calls)
    client.post(path+'/start',headers=h)
    assert len(calls)==before


def test_start_race_creates_one_attempt(client,roster,monkeypatch):
    item,_=draft(client,roster)
    publish(client,roster,item,monkeypatch)
    path=f"/api/platform/assignments/{item['id']}/start"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post(path,headers=roster['headers']['student']),range(2)))
    assert all(r.status_code==200 for r in responses)
    assert responses[0].json()['id']==responses[1].json()['id']


def test_archive_removes_student_access(client,roster,monkeypatch):
    item,_=draft(client,roster)
    publish(client,roster,item,monkeypatch)
    path=f"/api/platform/assignments/{item['id']}"
    assert client.post(path+'/archive',headers=roster['headers']['prof']).status_code==200
    assert client.get(path,headers=roster['headers']['student']).status_code==404
    assert client.post(path+'/publish',headers=roster['headers']['prof']).status_code==409


def test_milestone_hides_history_and_completes_on_submission(client,roster,monkeypatch):
    item,_=draft(client,roster,tool='reflections',config={'module_type':'milestone_based','milestone_prompt':'Reflect','historical_data':'name,challenge,solution\nPrivate name,issue,fix'})
    publish(client,roster,item,monkeypatch)
    path=f"/api/platform/assignments/{item['id']}";h=roster['headers']['student']
    assert 'Private name' not in client.get(path,headers=h).text
    client.post(path+'/start',headers=h)
    monkeypatch.setattr(engines,'call',lambda *a,**kw:{'similar':[{'challenge':'issue','solution':'fix'}]})
    res=client.post(path+'/messages',headers=h,json={'message':'My reflection','request_id':str(uuid4())})
    assert res.json()['status']=='completed'
    assert res.json()['result']['similar'][0]['solution']=='fix'
