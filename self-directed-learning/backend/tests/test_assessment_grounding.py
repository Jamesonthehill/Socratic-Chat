"""Local provenance, outcome coverage and rendering checks; no AI reviewer."""
import copy
import json

import httpx
import pytest

from app import bounded_flow, lesson_flow, openai_client
from app.assessment_flow import interview_prompt, validate_interview_questions
from app.lesson_content import configuration_issues
from app.schemas import LearningPlan
from test_short_assessment import short_plan
from test_short_assessment_unit import at_application, send


def grounded_plan():
    plan = short_plan()
    plan['assessment_grounding_version'] = 1
    for section in plan['application_sections']:
        section.update(objective_ids=[o['id'] for o in plan['objectives']], reasoning_criteria=[{
            'description': f"Explain the reasoning for {section['title']} using the scenario's actors and boundary.",
            'evidence_groups': [],
        }])
    return plan


def answers():
    return [
        {'id': 'identify', 'answer': 'Each individual book is a separate object.'},
        {'id': 'decide', 'answer': 'I would store availability on each book object.'},
        {'id': 'apply', 'answer': 'Only the borrowed book changes its availability.'},
    ]


def questions():
    return [
        {'purpose': 'justification', 'source_application_id': 'decide',
         'source_quote': 'store availability on each book object',
         'prompt': 'Why did you place that state on each object?', 'changed_condition': ''},
        {'purpose': 'changed_condition', 'source_application_id': 'apply',
         'source_quote': 'Only the borrowed book changes its availability.',
         'prompt': 'Would your design still distinguish which copy was borrowed? Explain why.',
         'changed_condition': 'The library now has two copies of the same title.'},
    ]


def test_grounded_sections_validate_and_old_sections_remain_compatible():
    assert not configuration_issues(grounded_plan())
    assert LearningPlan.model_validate(grounded_plan()).assessment_grounding_version == 1
    assert not configuration_issues(short_plan())


def test_student_lesson_detail_hides_section_criteria_and_instructor_keeps_them():
    from app.main import _assignment_public
    item = {'id': 'grounded', 'status': 'published', 'learning_plan': json.dumps(grounded_plan())}
    student = _assignment_public(item)['learning_plan']
    assert all(set(section) == {'id', 'title', 'prompt'} for section in student['application_sections'])
    instructor = _assignment_public(item, instructor_view=True)['learning_plan']
    assert instructor['application_sections'][0]['reasoning_criteria']
    assert instructor['application_sections'][0]['objective_ids']


@pytest.mark.parametrize('change', ['missing_mapping', 'unknown_mapping', 'duplicate_mapping', 'missing_criteria', 'blank_criteria', 'uncovered_objective'])
def test_publication_rejects_invalid_outcome_mapping_and_criteria(change):
    plan = grounded_plan()
    section = plan['application_sections'][0]
    if change == 'missing_mapping': section['objective_ids'] = []
    if change == 'unknown_mapping': section['objective_ids'] = ['unknown-objective']
    if change == 'duplicate_mapping': section['objective_ids'] *= 2
    if change == 'missing_criteria': section['reasoning_criteria'] = []
    if change == 'blank_criteria': section['reasoning_criteria'] = [{'description': '   ', 'evidence_groups': []}]
    if change == 'uncovered_objective':
        extra = copy.deepcopy(plan['objectives'][0])
        extra['id'] = 'uncovered'
        plan['objectives'].append(extra)
    assert any('Application section' in issue or 'application sections must cover' in issue for issue in configuration_issues(plan))


@pytest.mark.parametrize('change', ['unknown_source', 'wrong_source', 'invented_quote', 'partial_word_quote', 'blank_quote', 'generic_quote', 'same_purpose', 'reverse_purposes', 'missing_condition', 'unexpected_condition', 'repeat_prompt', 'punctuation_repeat', 'word_order_repeat'])
def test_interviews_reject_unverified_references_and_duplicate_purposes(change):
    proposed = questions()
    if change == 'unknown_source': proposed[0]['source_application_id'] = 'not-an-answer'
    if change == 'wrong_source': proposed[0]['source_application_id'] = 'identify'
    if change == 'invented_quote': proposed[0]['source_quote'] = 'I will share availability across every book.'
    if change == 'partial_word_quote': proposed[0]['source_quote'] = 'tore availability on each book object'
    if change == 'blank_quote': proposed[0]['source_quote'] = ' '
    if change == 'generic_quote': proposed[0]['source_quote'] = 'I'
    if change == 'same_purpose': proposed[1]['purpose'] = 'justification'
    if change == 'reverse_purposes': proposed.reverse()
    if change == 'missing_condition': proposed[1]['changed_condition'] = ' '
    if change == 'unexpected_condition': proposed[0]['changed_condition'] = 'A different case.'
    if change == 'repeat_prompt': proposed[1]['prompt'] = proposed[0]['prompt']
    if change == 'punctuation_repeat': proposed[1]['prompt'] = proposed[0]['prompt'].upper().replace('?', ' ! ')
    if change == 'word_order_repeat': proposed[1]['prompt'] = ' '.join(reversed(proposed[0]['prompt'].replace('?', '').split()))
    assert validate_interview_questions(proposed, answers()) is None


def test_valid_questions_render_verified_quote_and_changed_condition():
    checked = validate_interview_questions(questions(), answers())
    assert checked is not None
    assert answers()[1]['answer'].find(checked[0]['source_quote']) >= 0
    assert checked[0]['source_quote'] in interview_prompt(checked[0])
    assert checked[1]['changed_condition'] in interview_prompt(checked[1])
    assert interview_prompt('An older saved interview question?') == 'An older saved interview question?'
    short_answers = [{'id': 'brief', 'answer': 'No.'}]
    proposed = questions()
    for q in proposed:
        q.update(source_application_id='brief', source_quote='No.')
    assert validate_interview_questions(proposed, short_answers) is not None


def test_structured_questions_persist_and_criteria_are_hidden_but_used_in_grading(monkeypatch):
    state = at_application()
    state['lesson_snapshot'] = grounded_plan()
    plan = state['lesson_snapshot']
    public = lesson_flow.public_state(state)
    assert set(public['current_application']) == {'id', 'title', 'prompt'}
    monkeypatch.setattr(bounded_flow, 'generate_application_interview', lambda *args: validate_interview_questions(questions(), answers()))
    for section, answer in zip(plan['application_sections'], answers(), strict=True):
        state, _, _ = send(state, action='answer', question_id=section['id'], content=answer['answer'])
    public = lesson_flow.public_state(state)
    assert 'source_quote' not in public['current_interview']
    assert questions()[0]['source_quote'] in public['current_interview']['prompt']
    assert all('reasoning_criteria' not in a and 'objective_ids' not in a for a in public['application_answers'])
    state, _, _ = send(state, action='answer', question_id='interview-1', content='Availability belongs to a specific copy.')
    state, _, _ = send(state, action='pause')
    state, _, _ = send(state, action='resume')
    assert questions()[1]['changed_condition'] in lesson_flow.public_state(state)['current_interview']['prompt']
    captured = {}
    def grade(response, rubric, objective, material, prompt):
        captured.update(evidence=json.loads(response), prompt=prompt)
        return {'status': 'assessed', 'score': 1, 'feedback': 'Clear object state reasoning.'}
    monkeypatch.setattr(bounded_flow, 'assess_configured_response', grade)
    state, _, _ = send(state, action='answer', question_id='interview-2', content='Each copy has its own identifier.')
    assert state['stage'] == 'completed'
    assert captured['evidence']['interview'][0]['source_application_id'] == 'decide'
    assert plan['application_sections'][0]['reasoning_criteria'][0]['description'] in captured['prompt']


def test_real_generator_contract_accepts_structured_provenance(monkeypatch):
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    monkeypatch.setattr(openai_client, '_chat_settings', lambda: ('https://provider.invalid', 'model', {}))
    captured = {}
    class Provider:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            captured.update(kwargs['json'])
            return httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'), json={
                'choices': [{'message': {'content': json.dumps({'questions': questions()})}}]})
    monkeypatch.setattr(openai_client.httpx, 'Client', Provider)
    assert openai_client.generate_application_interview(grounded_plan(), answers()) == questions()
    payload = json.loads(captured['messages'][1]['content'])
    assert payload['application'] == answers()
    assert 'source_quote' in payload['question_schema']['properties']
