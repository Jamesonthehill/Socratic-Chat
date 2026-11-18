"""Synthetic, cross-topic interview and API isolation regressions; no live keys."""
import copy
import json
from uuid import uuid4

import httpx
import pytest

from app import application_interview as interview, bounded_flow
from test_api import client, headers, turn
from test_bounded_flow import bounded_plan, open_quiz


def completed_state():
    plan = bounded_plan()
    plan['application_rubric'] = [{'description': 'Explain your decision and its consequence.', 'evidence_groups': [['reason'], ['consequence']]}]
    return {'lesson_snapshot': plan, 'application_submission': 'I chose a queue because requests can arrive in bursts.',
            'application_assessment': {'score': 0.5}, 'quiz_score': 4}


def event(action, **kwargs):
    return interview.InterviewTurn(action=action, turn_id=str(uuid4()), **kwargs)


def question(context):
    return {'question': 'Why does your queue help when requests arrive in bursts?',
            'submission_quote': context['application_response'][:30]}


def assessment(context, sound=False):
    return {'evidence': [{'target_id': t['id'], 'status': 'met' if sound else 'partial',
                         'quote': context['latest_answer'], 'feedback': 'You linked a decision to an effect.'}
                        for t in context['evidence_targets']],
            'feedback': 'You explained a relevant effect. Consider how the constraint changes your decision.',
            'followup_question': '' if sound else f'How would a changed constraint affect your decision, case {context["followups_remaining"]}?',
            'followup_target_ids': [] if sound else [context['evidence_targets'][0]['id']]}


def install(monkeypatch, sound=False):
    def model(schema, instructions, context):
        return question(context) if schema is interview.QuestionOutput else assessment(context, sound)
    monkeypatch.setattr(interview, 'request_output', model)


def answer(state, content='The queue holds requests while the worker finishes its current request.'):
    return event('answer', question_id=state['application_interview']['questions'][-1]['id'], content=content)


def test_initial_and_two_followups_persist_evidence_without_changing_grades(monkeypatch):
    install(monkeypatch)
    state = completed_state()
    original = copy.deepcopy(state)
    interview.process_interview(state, event('start'))
    for _ in range(3):
        interview.process_interview(state, answer(state))
    audit = state['application_interview']
    assert len(audit['questions']) == len(audit['answers']) == 3
    assert audit['status'] == 'complete' and audit['outcome'] == 'needs_review'
    assert audit['started_at'] <= audit['answers'][0]['received_at'] <= audit['ended_at']
    assert audit['grade_publication'] == 'none'
    assert state['application_assessment'] == original['application_assessment']
    assert state['quiz_score'] == original['quiz_score']
    with pytest.raises(ValueError, match='ended'):
        interview.process_interview(state, answer(state))


def test_sound_reasoning_ends_without_unnecessary_followups(monkeypatch):
    install(monkeypatch, sound=True)
    state = completed_state()
    interview.process_interview(state, event('start'))
    interview.process_interview(state, answer(state))
    assert state['application_interview']['outcome'] == 'evidence_demonstrated'
    assert len(state['application_interview']['questions']) == 1


def test_duplicate_requests_and_reload_are_idempotent(monkeypatch):
    install(monkeypatch)
    state = completed_state()
    start = event('start')
    interview.process_interview(state, start)
    interview.process_interview(state, start)
    interview.process_interview(state, event('start'))
    response = answer(state)
    interview.process_interview(state, response)
    reloaded = json.loads(json.dumps(state))
    interview.process_interview(reloaded, response)
    assert len(reloaded['application_interview']['answers']) == 1
    with pytest.raises(ValueError, match='request ID'):
        interview.process_interview(reloaded, response.model_copy(update={'content':'Changed response'}))


@pytest.mark.parametrize('failure', ['timeout', 'missing_target', 'fake_quote', 'extra_field', 'repeat_followup'])
def test_failures_never_consume_a_followup_and_save_retry_response(monkeypatch, failure):
    install(monkeypatch)
    state = completed_state()
    interview.process_interview(state, event('start'))
    current_id = state['application_interview']['questions'][-1]['id']
    def bad(schema, instructions, context):
        if failure == 'timeout':
            raise httpx.ReadTimeout('synthetic failure')
        result = assessment(context)
        if failure == 'missing_target': result['evidence'].pop()
        if failure == 'fake_quote': result['evidence'][0]['quote'] = 'The learner never said this.'
        if failure == 'extra_field': result['grade'] = 100
        if failure == 'repeat_followup': result['followup_question'] = context['question']
        return result
    monkeypatch.setattr(interview, 'request_output', bad)
    response = answer(state)
    interview.process_interview(state, response)
    audit = state['application_interview']
    assert audit['status'] == 'active' and not audit['answers']
    assert audit['questions'][-1]['id'] == current_id
    assert audit['failures'][0]['response'] == response.content
    assert interview.public_interview(audit)['retry_response'] == response.content
    install(monkeypatch)
    interview.process_interview(state, answer(state))
    assert len(audit['answers']) == 1


def test_blank_stale_and_stopped_interviews(monkeypatch):
    install(monkeypatch)
    state = completed_state()
    interview.process_interview(state, event('start'))
    with pytest.raises(ValueError, match='reasoning'):
        interview.process_interview(state, answer(state, ' '))
    with pytest.raises(ValueError, match='current'):
        interview.process_interview(state, event('answer', question_id='other-question', content='Reasoning'))
    interview.process_interview(state, event('stop'))
    assert state['application_interview']['status'] == 'stopped'
    assert state['application_interview']['ended_at']
    assert state['application_assessment']['score'] == 0.5


def test_question_personalization_evidence_is_validated(monkeypatch):
    monkeypatch.setattr(interview, 'request_output', lambda *a: {'question':'Why choose that?', 'submission_quote':'Fabricated claim'})
    state = completed_state()
    interview.process_interview(state, event('start'))
    assert state['application_interview']['status'] == 'pending'
    assert not state['application_interview']['questions']
    assert interview.public_interview(state['application_interview'])['error']


def complete(client, monkeypatch):
    plan = bounded_plan()
    aid = open_quiz(client, plan)
    for q in plan['diagnostic_quiz']:
        turn(client, aid, action='answer', option_index=q['correct_index'])
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a, **kw: {
        'status':'assessed', 'score':0.5, 'what_went_well':'You explained a choice.',
        'what_was_incorrect':'You omitted one consequence.', 'how_to_improve':'Explain the consequence.'})
    result = turn(client, aid, action='answer', content='I chose a queue because requests arrive in bursts.')
    return aid, result


def test_api_save_reload_access_and_completion_card_unchanged(client, monkeypatch):
    monkeypatch.setenv('SDL_APPLICATION_INTERVIEW_ENABLED', 'true')
    install(monkeypatch, sound=True)
    aid, before = complete(client, monkeypatch)
    url = f'/api/student/assignments/{aid}/application-interview'
    start = event('start').model_dump()
    assert client.post(url, json=start).status_code == 401
    assert client.post(url, headers=headers('instructor-demo'), json=start).status_code == 403
    assert client.post(url, headers=headers('student-jordan'), json=start).status_code == 409
    first = client.post(url, headers=headers(), json=start)
    assert first.status_code == 200, first.text
    assert first.json()['status'] == 'active'
    second = client.post(url, headers=headers(), json=event('answer', content='A queue buffers arrivals.', question_id=first.json()['question']['id']).model_dump())
    assert second.status_code == 200, second.text
    refreshed = client.get(f'/api/student/assignments/{aid}/attempt', headers=headers()).json()
    assert refreshed['learning_state']['application_interview']['status'] == 'complete'
    assert refreshed['completed_at'] == before['completed_at']
    assert refreshed['quiz_score'] == before['quiz_score']
    assert refreshed['learning_state']['completion_code'] == before['learning_state']['completion_code']
    public = json.dumps(refreshed['learning_state']['application_interview'])
    assert 'evidence_targets' not in public and 'criterion_index' not in public
    report = client.get(f'/api/instructor/assignments/{aid}/students/student-alex', headers=headers('instructor-demo'))
    assert report.status_code == 200
    assert client.get(f'/api/instructor/assignments/{aid}/students/student-alex', headers=headers()).status_code == 403
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN', 'interview-test-token')
    report_url = f'/internal/platform/lessons/{aid}/application-interviews'
    assert client.get(report_url).status_code == 401
    audit = client.get(report_url, headers={'X-Platform-Service':'interview-test-token'})
    assert audit.status_code == 200
    assert next(row for row in audit.json() if row['student_id'] == 'student-alex')['interview']['answers'][0]['assessment']['evidence']
    monkeypatch.setenv('SDL_APPLICATION_INTERVIEW_ENABLED', 'false')
    assert client.post(url, headers=headers(), json=start).status_code == 404


def test_two_students_have_distinct_interviews_and_cannot_submit_each_others_question(client, monkeypatch):
    monkeypatch.setenv('SDL_APPLICATION_INTERVIEW_ENABLED', 'true')
    install(monkeypatch)
    aid, _ = complete(client, monkeypatch)
    from app.db import connection
    with connection() as conn:
        alex = dict(conn.execute('SELECT * FROM attempts WHERE assignment_id=? AND student_id=?', (aid,'student-alex')).fetchone())
        conn.execute('INSERT INTO attempts(id,assignment_id,student_id,status,phase,learning_state,started_at) VALUES (?,?,?,?,?,?,?)',
                     (str(uuid4()),aid,'student-jordan','completed','completed',alex['learning_state'],alex['started_at']))
    url = f'/api/student/assignments/{aid}/application-interview'
    a = client.post(url, headers=headers(), json=event('start').model_dump()).json()
    b = client.post(url, headers=headers('student-jordan'), json=event('start').model_dump()).json()
    assert a['question']['id'] != b['question']['id']
    stolen = event('answer', question_id=a['question']['id'], content='Some reasoning').model_dump()
    assert client.post(url, headers=headers('student-jordan'), json=stolen).status_code == 409
    assert client.post(url, headers=headers(), json=event('stop').model_dump()).json()['status'] == 'stopped'
    saved_b = client.get(f'/api/student/assignments/{aid}/attempt', headers=headers('student-jordan')).json()
    assert saved_b['learning_state']['application_interview']['status'] == 'active'


def test_api_outage_retry_and_stop_survive_reload_without_grading(client, monkeypatch):
    monkeypatch.setenv('SDL_APPLICATION_INTERVIEW_ENABLED', 'true')
    install(monkeypatch)
    aid, before = complete(client, monkeypatch)
    url = f'/api/student/assignments/{aid}/application-interview'
    first = client.post(url, headers=headers(), json=event('start').model_dump()).json()
    def unavailable(*args):
        raise httpx.ReadTimeout('synthetic')
    monkeypatch.setattr(interview, 'request_output', unavailable)
    request = event('answer', question_id=first['question']['id'], content='My saved explanation.').model_dump()
    failed = client.post(url, headers=headers(), json=request)
    assert failed.status_code == 200 and failed.json()['error']
    replay = client.post(url, headers=headers(), json=request)
    assert replay.json() == failed.json()
    saved = client.get(f'/api/student/assignments/{aid}/attempt', headers=headers()).json()
    current = saved['learning_state']['application_interview']
    assert current['answered_count'] == 0 and current['retry_response'] == request['content']
    assert current['question']['id'] == first['question']['id']
    assert saved['completed_at'] == before['completed_at']
    stop = client.post(url, headers=headers(), json=event('stop').model_dump()).json()
    assert stop['status'] == 'stopped' and stop['ended_at']
    saved = client.get(f'/api/student/assignments/{aid}/attempt', headers=headers()).json()
    assert saved['learning_state']['completion_code'] == before['learning_state']['completion_code']
    assert saved['learning_state']['application_interview']['status'] == 'stopped'


def test_identity_resolver_rejects_aliasing_different_platform_ids(client, monkeypatch):
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','identity-test-token')
    url = '/internal/platform/students/resolve'
    h = {'X-Platform-Service':'identity-test-token'}
    body = {'platform_user_id':'student-alex', 'email':'alex@example.edu', 'display_name':'Alex'}
    from app.db import connection
    with connection() as conn:
        body['email'] = conn.execute('SELECT email FROM users WHERE id=?', ('student-alex',)).fetchone()['email']
    assert client.post(url, headers=h, json=body).status_code == 200
    assert client.post(url, headers=h, json={**body,'platform_user_id':'another-user'}).status_code == 409


@pytest.mark.parametrize('case', ['success', 'refusal', 'truncated', 'invalid_schema', 'auth_failure', 'transient'])
def test_real_transport_uses_strict_schema_and_handles_provider_failures(monkeypatch, case):
    calls = []
    real_client = httpx.Client
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body['response_format']['json_schema']['strict'] is True
        assert body['response_format']['json_schema']['schema']['additionalProperties'] is False
        assert body['messages'][0]['role'] == 'system'
        assert body['messages'][1]['role'] == 'user'
        assert json.loads(body['messages'][1]['content'])['application_response'] == 'Untrusted learner text'
        if case == 'auth_failure':
            return httpx.Response(401,json={'error':{'message':'invalid synthetic key'}})
        if case == 'transient' and len(calls) == 1:
            return httpx.Response(503,json={'error':{'message':'synthetic outage'}})
        output = {'question':'Why did you choose this boundary?', 'submission_quote':'Untrusted learner text'}
        if case == 'invalid_schema': output['question'] = 'Why this? Why that?'
        return httpx.Response(200,json={'choices':[{'finish_reason':'length' if case == 'truncated' else 'stop',
            'message':{'refusal':'Cannot help' if case == 'refusal' else None,'content':json.dumps(output)}}]})
    monkeypatch.setattr(interview.ai,'runtime_ai_mode',lambda:'openai')
    monkeypatch.setattr(interview.ai,'_chat_settings',lambda:('https://api.example.test','synthetic-model',{'Authorization':'Bearer synthetic'}))
    monkeypatch.setattr(interview.httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    if case in {'success','transient'}:
        result = interview.request_output(interview.QuestionOutput,interview.QUESTION_INSTRUCTIONS,{'application_response':'Untrusted learner text'})
        assert result['question'].count('?') == 1
    else:
        with pytest.raises((ValueError,httpx.HTTPError)):
            interview.request_output(interview.QuestionOutput,interview.QUESTION_INSTRUCTIONS,{'application_response':'Untrusted learner text'})
    assert len(calls) == (2 if case == 'transient' else 1)
