"""Synchronous checks run without an ASGI server or loopback sockets."""
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app import bounded_flow, lesson_flow, openai_client
from app.lesson_content import configuration_issues
from app.schemas import LearningPlan, LearningTurn
from test_short_assessment import short_plan


def send(state, **fields):
    # Exercise state round-tripping, as used by persisted attempt snapshots.
    state = json.loads(json.dumps(state))
    return lesson_flow.process_lesson_turn(state, LearningTurn(turn_id='unit-turn', **fields))


def at_application():
    plan = short_plan()
    state = lesson_flow.initial_state(plan)
    state, _, _ = send(state, action='continue')
    state, _, _ = send(state, action='continue')
    for q in plan['diagnostic_quiz']:
        state, reply, _ = send(state, action='answer', question_id=q['id'], option_index=q['correct_index'])
    assert '3/3' in reply
    return state


def at_interview(monkeypatch):
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: ['Why this decision?', 'What if the request is cancelled?'])
    state = at_application()
    for section in state['lesson_snapshot']['application_sections']:
        state, _, _ = send(state, action='answer', question_id=section['id'], content='A customer requests a delivery.')
    return state


def test_versioned_validation_preserves_old_plans_and_rejects_wrong_counts():
    plan = short_plan()
    assert not configuration_issues(plan)
    assert LearningPlan.model_validate(plan).assessment_version == 2
    old = json.loads((Path(__file__).parents[1] / 'lessons/requirements.json').read_text(encoding='utf-8'))
    assert LearningPlan.model_validate(old).assessment_version == 1
    assert not configuration_issues(old)
    plan['application_sections'] = plan['application_sections'][:2]
    assert any('three' in issue or '3 application' in issue for issue in configuration_issues(plan))
    plan = short_plan()
    plan['diagnostic_quiz'].append(plan['diagnostic_quiz'][0])
    assert any('three questions' in issue for issue in configuration_issues(plan))


def test_application_answers_save_separately_and_current_question_is_public(monkeypatch):
    state = at_application()
    state, reply, _ = send(state, action='answer', question_id='identify', content='The customer.')
    assert reply.startswith('Saved.')
    state, _, _ = send(state, action='pause')
    state, _, _ = send(state, action='resume')
    public = lesson_flow.public_state(state)
    assert public['current_application']['id'] == 'decide'
    assert public['application_answers'][0]['answer'] == 'The customer.'
    assert public['quiz_count'] == 3
    assert 'lesson_snapshot' not in public
    assert 'application_rubric' not in public


def test_interview_requires_two_answers_and_grades_combined_evidence(monkeypatch):
    state = at_interview(monkeypatch)
    public = lesson_flow.public_state(state)
    assert public['current_interview']['id'] == 'interview-1'
    assert 'interview_questions' not in public
    seen = {}
    def grade(response, *args):
        seen['evidence'] = json.loads(response)
        return {'status': 'assessed', 'score': 1, 'feedback': 'Clear reasoning.'}
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', grade)
    state, _, _ = send(state, action='answer', question_id='interview-1', content='It fits the system responsibility.')
    assert state['stage'] == 'interview'
    assert not seen
    state, _, _ = send(state, action='pause')
    state, _, _ = send(state, action='resume')
    state, reply, _ = send(state, action='answer', question_id='interview-2', content='Cancellation changes the order state.')
    assert state['stage'] == 'completed'
    assert 'Clear reasoning.' in reply
    assert len(seen['evidence']['application']) == 3
    assert len(seen['evidence']['interview']) == 2
    assert 'customer' in state['application_submission']
    saved = json.loads(json.dumps(state))
    assert len(saved['completion_feedback']['cards']) == 4
    assert lesson_flow.public_state(saved)['completion_feedback'] == state['completion_feedback']
    # Old saved completions get the same four-card shape without another AI call.
    del saved['completion_feedback']
    assert len(lesson_flow.public_state(saved)['completion_feedback']['cards']) == 4


def test_generation_and_assessment_retry_preserve_submitted_answers(monkeypatch):
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: None)
    state = at_application()
    for section in state['lesson_snapshot']['application_sections']:
        state, _, _ = send(state, action='answer', question_id=section['id'], content='A short answer.')
    assert lesson_flow.public_state(state)['interview_retry']
    assert len(state['application_answers']) == 3
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: ['Why this choice?', 'What if circumstances change?'])
    state, _, _ = send(state, action='continue')
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a: {'status': 'grader_unavailable'})
    for i in range(2):
        state, _, _ = send(state, action='answer', question_id=f'interview-{i+1}', content='Brief justification.')
    assert state['stage'] == 'interview'
    assert len(state['interview_answers']) == 2
    assert lesson_flow.public_state(state)['interview_retry']
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a: {'status': 'assessed', 'score': 0.5, 'feedback': 'Review boundaries.'})
    state, _, _ = send(state, action='continue')
    assert state['stage'] == 'completed'
    assert len(state['interview_answers']) == 2


def test_stale_and_empty_answers_do_not_advance():
    state = at_application()
    with pytest.raises(ValueError, match='current application'):
        send(state, action='answer', question_id='decide', content='Out of order.')
    state, _, _ = send(state, action='answer', question_id='identify', content='  ')
    assert not state['application_answers']


def test_legacy_bounded_lesson_keeps_five_questions_and_one_submission(monkeypatch):
    from test_bounded_flow import bounded_plan
    plan = bounded_plan()
    state = lesson_flow.initial_state(plan)
    state, _, _ = send(state, action='continue')
    state, _, _ = send(state, action='continue')
    for q in plan['diagnostic_quiz']:
        state, reply, _ = send(state, action='answer', question_id=q['id'], option_index=q['correct_index'])
    assert '5/5' in reply
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a, **kw: {'status': 'assessed', 'score': 1, 'feedback': 'Clear.', 'what_went_well':'Clear.', 'what_was_incorrect':'No errors.', 'how_to_improve':'Explain the tradeoff.'})
    state, _, _ = send(state, action='answer', content='A single application answer.')
    assert state['stage'] == 'completed'
    assert state['application_submission'] == 'A single application answer.'
    assert 'interview_questions' not in state


def test_short_authoring_requests_three_mcqs_and_three_sections(monkeypatch):
    plan = short_plan()
    for section in plan['application_sections']:
        section.update(objective_ids=[o['id'] for o in plan['objectives']],
                       reasoning_criteria=[{'description': 'Explain the scenario-specific reasoning.', 'evidence_groups': []}])
    from app import edumind_quiz
    plan['objectives'][0]['id'] = 'OBJ1'
    plan['learning_assets'][0]['objective_id'] = 'OBJ1'
    for section in plan['application_sections']:
        section['objective_ids'] = ['OBJ1']
    calls = []
    def quiz(*args, **kwargs):
        calls.append(kwargs['levels'])
        return plan['diagnostic_quiz']
    monkeypatch.setattr(edumind_quiz, 'generate_quiz', quiz)
    seen = {}
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(openai_client, '_chat_settings', lambda: ('https://provider.invalid', 'model', {}))
    class Provider:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            seen.update(kwargs['json'])
            return httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'), json={
                'choices': [{'message': {'content': json.dumps(plan)}}]})
    monkeypatch.setattr(openai_client.httpx, 'Client', Provider)
    generated = openai_client.generate_learning_plan(plan['topic'], 'Undergraduate',
        approved_material=plan['approved_material'], objective_descriptions=[o['description'] for o in plan['objectives']],
        study_resources=plan['study_resources'], intended_difficulty=plan['intended_difficulty'],
        prerequisite_knowledge=plan['prerequisite_knowledge'], short_assessment=True)
    assert generated['assessment_version'] == 2
    assert generated['assessment_grounding_version'] == 1
    asset_fields = seen['response_format']['json_schema']['schema']['$defs']['ObjectiveLearningAssets']['properties']
    for level in ('foundational','standard','accelerated'):
        assert level not in asset_fields
        assert all(asset[level] == [] for asset in generated['learning_assets'])
    assert generated['learning_assets'][0]['explanation'] == plan['learning_assets'][0]['explanation']
    assert generated['learning_assets'][0]['worked_example'] == plan['learning_assets'][0]['worked_example']
    assert len(generated['diagnostic_quiz']) == 3
    assert len(generated['application_sections']) == 3
    schema = seen['response_format']['json_schema']['schema']['properties']
    assert 'diagnostic_quiz' not in schema
    assert calls == [['foundational', 'understanding', 'application']]
    assert schema['application_sections']['minItems'] == schema['application_sections']['maxItems'] == 3
    section_schema = seen['response_format']['json_schema']['schema']['$defs']['ApplicationSection']['properties']
    assert section_schema['objective_ids']['minItems'] == 1
    assert section_schema['reasoning_criteria']['minItems'] == 1


def test_database_roundtrip_completion_and_duplicate_turns(tmp_path, monkeypatch):
    from app import config, db, main
    from app.schemas import AssignmentInput
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(config, 'UPLOAD_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(db, 'DATABASE_URL', '')
    monkeypatch.setattr(db, 'DATABASE_PATH', tmp_path / 'test.sqlite3')
    db.initialize()
    instructor = {'id': 'instructor-demo', 'role': 'instructor', 'display_name': 'Instructor'}
    student = {'id': 'student-alex', 'role': 'student', 'display_name': 'Alex'}
    plan = short_plan()
    created = main.create_assignment(AssignmentInput(title=plan['title'], learning_plan=plan, student_ids=[student['id']]), instructor)
    aid = created['id']
    main.publish_assignment(aid, instructor)
    assert 'application_rubric' not in main.student_assignment_detail(aid, student)['learning_plan']
    main.start_attempt(aid, student)
    def submit(**fields):
        return main.learning_turn(aid, LearningTurn(turn_id=str(uuid4()), **fields), student)
    submit(action='continue')
    submit(action='continue')
    for q in plan['diagnostic_quiz']:
        result = submit(action='answer', question_id=q['id'], option_index=q['correct_index'])
    assert result['quiz_score'] == 3
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *a: ['Why this choice?', 'What if the order is cancelled?'])
    for section in plan['application_sections']:
        result = submit(action='answer', question_id=section['id'], content='The customer requests a delivery.')
    reopened = main.start_attempt(aid, student)
    assert reopened['learning_state']['current_interview']['id'] == 'interview-1'
    assert len(reopened['learning_state']['application_answers']) == 3
    submit(action='answer', question_id='interview-1', content='It matches the boundary.')
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', lambda *a: {'status': 'assessed', 'score': 1, 'feedback': 'Clear reasoning.'})
    body = LearningTurn(turn_id=str(uuid4()), action='answer', question_id='interview-2', content='Cancellation changes the order state.')
    completed = main.learning_turn(aid, body, student)
    replayed = main.learning_turn(aid, body, student)
    assert completed['status'] == 'completed'
    assert completed['completed_at'] == replayed['completed_at']
    assert completed['messages'] == replayed['messages']
    assert len(completed['learning_state']['interview_answers']) == 2
    assert '3/3' in main.instructor_student_evidence(aid, student['id'], instructor)['summary']['overview']


@pytest.mark.parametrize('questions', [[], ['Only one'], ['Same', 'Same'], ['Valid', '  '], ['Valid', 12]])
def test_malformed_provider_interviews_are_retriable(monkeypatch, questions):
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(openai_client, '_chat_settings', lambda: ('https://provider.invalid', 'model', {}))
    class Provider:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            return httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'), json={
                'choices': [{'message': {'content': json.dumps({'questions': questions})}}]})
    monkeypatch.setattr(openai_client.httpx, 'Client', Provider)
    assert openai_client.generate_application_interview(short_plan(), [{'answer': 'A'}, {'answer': 'B'}, {'answer': 'C'}]) is None
