"""API coverage for new 3–3–2 lessons, persistence and provider recovery."""
from uuid import uuid4

from test_api import client, headers, turn
from test_bounded_flow import bounded_plan, open_quiz


def short_plan():
    plan = bounded_plan()
    plan.update(assessment_version=2, application_sections=[
        {'id': 'identify', 'title': 'Identify', 'prompt': 'Who interacts with this delivery system?'},
        {'id': 'decide', 'title': 'Decide', 'prompt': 'Which interactions belong inside its boundary?'},
        {'id': 'apply', 'title': 'Apply', 'prompt': 'Describe how a customer requests a delivery.'},
    ])
    plan['diagnostic_quiz'] = plan['diagnostic_quiz'][:3]
    return plan


def application(client):
    plan = short_plan()
    aid = open_quiz(client, plan)
    for q in plan['diagnostic_quiz']:
        result = turn(client, aid, action='answer', question_id=q['id'], option_index=q['correct_index'])
    assert result['phase'] == 'application'
    assert result['quiz_score'] == 3
    assert '3/3' in result['messages'][-1]['content']
    return aid, plan


def answer_application(client, aid, plan):
    for section in plan['application_sections']:
        result = turn(client, aid, action='answer', question_id=section['id'], content='The customer requests a delivery inside the system boundary.')
    return result


def test_three_three_two_saves_resumes_and_grades_combined_evidence(client, monkeypatch):
    from app import bounded_flow
    seen = {}
    def interview(plan, answers):
        seen['application'] = answers
        return ['Why did you choose that boundary?', 'What if the delivery is cancelled?']
    def assess(response, *args):
        seen['evidence'] = response
        return {'status': 'assessed', 'score': 0.8, 'feedback': 'Clear actors; explain cancellation.'}
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', interview)
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', assess)
    aid, plan = application(client)
    first = turn(client, aid, action='answer', question_id='identify', content='A customer.')
    assert len(first['learning_state']['application_answers']) == 1
    assert 'feedback' not in first['messages'][-1]['content'].lower()
    turn(client, aid, action='pause')
    resumed = turn(client, aid, action='resume')
    assert resumed['learning_state']['current_application']['id'] == 'decide'
    for section in plan['application_sections'][1:]:
        result = turn(client, aid, action='answer', question_id=section['id'], content='The customer places an order.')
    assert result['phase'] == 'interview'
    assert result['status'] != 'completed'
    assert len(seen['application']) == 3
    assert 'interview_questions' not in result['learning_state']
    assert result['learning_state']['current_interview']['id'] == 'interview-1'
    turn(client, aid, action='answer', question_id='interview-1', content='It matches the responsibility of the system.')
    turn(client, aid, action='pause')
    resumed = turn(client, aid, action='resume')
    assert resumed['learning_state']['current_interview']['id'] == 'interview-2'
    url = f'/api/student/assignments/{aid}/learning-turn'
    body = {'action': 'answer', 'question_id': 'interview-2', 'content': 'Cancellation changes the order state.', 'turn_id': str(uuid4())}
    final = client.post(url, headers=headers(), json=body)
    assert final.status_code == 200, final.text
    assert final.json()['status'] == 'completed'
    cards = final.json()['learning_state']['completion_feedback']
    assert len(cards['cards']) == 4
    resumed_final = client.post(f'/api/student/assignments/{aid}/start', headers=headers()).json()
    assert resumed_final['learning_state']['completion_feedback'] == cards
    assert 'Cancellation changes' in seen['evidence']
    assert 'A customer.' in seen['evidence']
    replay = client.post(url, headers=headers(), json=body)
    assert replay.json()['messages'] == final.json()['messages']
    assert replay.json()['learning_state']['completion_feedback'] == cards
    assert replay.json()['completed_at'] == final.json()['completed_at']
    report = client.get(f'/api/instructor/assignments/{aid}/students/student-alex', headers=headers('instructor-demo')).json()
    assert '3/3' in report['summary']['overview']


def test_provider_retries_preserve_answers_and_do_not_add_rounds(client, monkeypatch):
    from app import bounded_flow
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: None)
    aid, plan = application(client)
    result = answer_application(client, aid, plan)
    assert result['phase'] == 'interview'
    assert result['learning_state']['interview_retry']
    assert len(result['learning_state']['application_answers']) == 3
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: ['Why this choice?', 'What if the customer cancels?'])
    result = turn(client, aid, action='continue')
    assert result['learning_state']['current_interview']['id'] == 'interview-1'
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a: {'status': 'grader_unavailable'})
    turn(client, aid, action='answer', question_id='interview-1', content='It fits the boundary.')
    result = turn(client, aid, action='answer', question_id='interview-2', content='I would record cancellation.')
    assert result['status'] != 'completed'
    assert result['learning_state']['interview_retry']
    assert len(result['learning_state']['interview_answers']) == 2
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a: {'status': 'assessed', 'score': 1, 'feedback': 'Clear reasoning.'})
    result = turn(client, aid, action='continue')
    assert result['status'] == 'completed'
    assert len(result['learning_state']['interview_answers']) == 2


def test_stale_and_blank_answers_do_not_advance(client):
    aid, plan = application(client)
    url = f'/api/student/assignments/{aid}/learning-turn'
    bad = client.post(url, headers=headers(), json={'action': 'answer', 'question_id': 'decide', 'content': 'Wrong section', 'turn_id': str(uuid4())})
    assert bad.status_code == 409
    blank = turn(client, aid, action='answer', question_id='identify', content='   ')
    assert blank['learning_state']['current_application']['id'] == 'identify'
    assert not blank['learning_state']['application_answers']


def test_compact_lesson_keeps_quiz_hints_and_completes_three_three_two(client,monkeypatch):
    from app import bounded_flow
    from app.schemas import LearningPlan
    from test_bounded_flow import open_quiz
    from test_api import turn,headers
    plan=short_plan()
    for asset in plan['learning_assets']:
        for level in ('foundational','standard','accelerated'):asset[level]=[]
    LearningPlan.model_validate(plan)
    monkeypatch.setattr(bounded_flow,'generate_application_interview',lambda *a:['Why does your decision fit this case?','What changes if the requested feature is cancelled?'])
    monkeypatch.setattr(bounded_flow,'assess_configured_response',lambda *a,**k:{'status':'assessed','score':0.8,'feedback':'You justified the decision.'})
    aid=open_quiz(client,plan)
    hint=turn(client,aid,action='hint',question_id=plan['diagnostic_quiz'][0]['id'])
    assert hint['learning_state']['stage']=='diagnostic_quiz'
    for q in plan['diagnostic_quiz']:result=turn(client,aid,action='answer',question_id=q['id'],option_index=q['correct_index'])
    assert result['learning_state']['stage']=='application'
    assert result['quiz_score']==3
    for section in plan['application_sections']:result=turn(client,aid,action='answer',question_id=section['id'],content='A customer requests a delivery inside the system boundary.')
    assert result['learning_state']['stage']=='interview'
    for index in range(2):result=turn(client,aid,action='answer',question_id=f'interview-{index+1}',content='This matches the responsibility of the system.')
    assert result['learning_state']['stage']=='completed'
    assert result['quiz_score']==3
    resumed=client.post(f'/api/student/assignments/{aid}/start',headers=headers()).json()
    assert resumed['learning_state']['stage']=='completed'
