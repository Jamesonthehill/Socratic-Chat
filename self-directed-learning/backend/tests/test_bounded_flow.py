from uuid import uuid4

from test_api import client, create, headers, lesson, turn


def bounded_plan():
    plan = lesson()
    plan.update(bounded_flow=True, starting_point='Identify requirements',
                ending_point='Apply requirements to a new delivery service',
                prerequisite_resources=plan['study_resources'],
                application_rubric=plan['objectives'][0]['rubric'])
    return plan


def open_quiz(client, plan):
    aid = create(client, plan)
    start = client.post(f'/api/student/assignments/{aid}/start', headers=headers())
    assert start.status_code == 200
    assert 'Prerequisites:' in start.json()['messages'][-1]['content']
    assert turn(client, aid, 'I am done')['phase'] == 'welcome'
    assert turn(client, aid, action='continue')['phase'] == 'study_resources'
    assert turn(client, aid, action='continue')['phase'] == 'diagnostic_quiz'
    return aid


def test_three_attempts_support_and_completion_are_persistent(client, monkeypatch):
    from app import bounded_flow
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a, **kw: {
        'status': 'assessed', 'category': 'partial_understanding', 'score': 0.5,
        'feedback': 'Identify the customer and justify the system boundary.', 'what_went_well': 'You identified the customer.', 'what_was_incorrect': 'No specific incorrect claim was identified.', 'how_to_improve': 'Justify the system boundary.'})
    plan = bounded_plan()
    aid = open_quiz(client, plan)
    q = plan['diagnostic_quiz'][0]
    wrong = (q['correct_index'] + 1) % 4
    first = turn(client, aid, action='answer', question_id=q['id'], option_index=wrong)
    assert first['learning_state']['quiz_index'] == 0
    assert 'Not quite.' in first['messages'][-1]['content']
    assert q['distractor_misconceptions'][wrong] in first['messages'][-1]['content']
    assert q['hint'] in first['messages'][-1]['content']
    assert first['learning_state']['quiz_feedback'][-1]['correct_index'] is None
    assert len(first['learning_state']['quiz_cards']) == 1
    assert q['explanation'] not in first['messages'][-1]['content']
    hint = turn(client, aid, action='hint', question_id=q['id'])
    assert 'Worked example' in hint['messages'][-1]['content']
    assert hint['learning_state']['quiz_attempt_count'] == 1
    reading = turn(client, aid, 'Read more', question_id=q['id'])
    assert 'Review:' in reading['messages'][-1]['content']
    assert reading['learning_state']['quiz_readings'][-1]['question_id'] == q['id']
    assert reading['learning_state']['quiz_readings'][-1]['message_index'] == len(reading['messages']) - 2
    turn(client, aid, action='answer', question_id=q['id'], option_index=wrong)
    third = turn(client, aid, action='answer', question_id=q['id'], option_index=wrong)
    assert third['learning_state']['quiz_index'] == 1
    assert 'The correct answer is' in third['messages'][-1]['content']
    assert 'attempts' not in third['messages'][-1]['content']
    for question in plan['diagnostic_quiz'][1:]:
        result = turn(client, aid, action='answer', question_id=question['id'], option_index=question['correct_index'])
        assert 'Correct.' in result['messages'][-1]['content']
    assert result['phase'] == 'quiz_review'
    result = turn(client, aid, action='continue')
    assert result['phase'] == 'application'
    assert result['quiz_score'] == 4
    assert result['quiz_results'][0]['assistance_used']
    assert result['status'] != 'completed'
    body = {'action': 'answer', 'content': 'The customer places a delivery order.', 'turn_id': str(uuid4())}
    url = f'/api/student/assignments/{aid}/learning-turn'
    final = client.post(url, headers=headers(), json=body)
    assert final.status_code == 200, final.text
    assert final.json()['status'] == 'completed'
    assert final.json()['required_task_submission'] == body['content']
    assert final.json()['completed_at']
    assert final.json()['learning_state']['completion_code'].startswith('SDL-')
    assert sum(q['attempts'] for q in final.json()['learning_state']['quiz_attempt_summary']) == 7
    assert len(final.json()['learning_state']['quiz_cards']) == 5
    assert 'What you got right' in final.json()['messages'][-1]['content']
    assert 'What you got wrong' in final.json()['messages'][-1]['content']
    assert 'How to improve' in final.json()['messages'][-1]['content']
    replay = client.post(url, headers=headers(), json=body)
    assert replay.status_code == 200
    assert len(replay.json()['messages']) == len(final.json()['messages'])
    assert replay.json()['completed_at'] == final.json()['completed_at']
    assert replay.json()['learning_state']['completion_code'] == final.json()['learning_state']['completion_code']
    assert client.post(url, headers=headers(), json={**body, 'turn_id': str(uuid4())}).status_code == 409
    report = client.get(f'/api/instructor/assignments/{aid}/students/student-alex', headers=headers('instructor-demo'))
    assert report.status_code == 200, report.text
    assert 'First-attempt quiz score' in report.json()['summary']['overview']
    assert report.json()['attempt']['learning_state']['application_assessment']['score'] == 0.5


def test_retry_correct_counts_first_attempt_only_and_pause_resumes(client):
    plan = bounded_plan()
    aid = open_quiz(client, plan)
    question = plan['diagnostic_quiz'][0]
    turn(client, aid, action='answer', option_index=(question['correct_index'] + 1) % 4)
    assert turn(client, aid, action='pause')['phase'] == 'paused'
    resumed = turn(client, aid, action='resume')
    assert resumed['learning_state']['quiz_attempt_count'] == 1
    answered = turn(client, aid, action='answer', option_index=question['correct_index'])
    assert answered['learning_state']['quiz_index'] == 1
    assert answered['quiz_score'] == 0


def test_generation_uses_boundaries_and_prerequisite_readings(client, monkeypatch):
    from app import main
    plan = lesson()
    seen = {}
    def infer(material, filename):
        seen['material'] = material
        return {'topic': plan['topic'], 'objective_descriptions': ['Original'], 'prerequisite_knowledge': 'Actors and systems'}
    def generate(*args, **kwargs):
        seen.update(kwargs)
        return plan
    monkeypatch.setattr(main, 'infer_document_context', infer)
    monkeypatch.setattr(main, 'generate_learning_plan', generate)
    monkeypatch.setattr(main, 'discover_resources', lambda *a: plan['study_resources'])
    monkeypatch.setattr(main, 'verify_resources', lambda resources, topic: resources)
    monkeypatch.setattr(main, 'read_resource_excerpts', lambda *a: [])
    generated = main._document_plan(plan['approved_material'], 'slides.pptx', starting_point='Basic actors', ending_point='Describe a use case')
    assert generated['bounded_flow']
    assert generated['prerequisite_resources']
    assert 'Basic actors' in seen['material']
    assert seen['objective_descriptions'] == ['Describe a use case']


def test_editable_openings_and_question_hint_example(client):
    plan = bounded_plan()
    plan.update(prerequisite_message="Welcome! Review these assumptions.", study_message="Let's work through this instructor-authored example.")
    plan['diagnostic_quiz'][0]['worked_example'] = 'A custom library example for this question.'
    aid = create(client, plan)
    initial = client.post(f'/api/student/assignments/{aid}/start', headers=headers()).json()
    assert initial['messages'][-1]['content'] == plan['prerequisite_message']
    study = turn(client, aid, action='continue')
    assert study['messages'][-1]['content'] == plan['study_message']
    quiz = turn(client, aid, action='continue')
    assert 'Question 1' not in quiz['messages'][-1]['content']
    assert 'attempts' not in quiz['messages'][-1]['content']
    hint = turn(client, aid, action='hint')
    assert plan['diagnostic_quiz'][0]['worked_example'] in hint['messages'][-1]['content']
