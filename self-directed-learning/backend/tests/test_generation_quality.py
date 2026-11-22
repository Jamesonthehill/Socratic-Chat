"""Composition and structural coverage checks, without claiming semantic review."""
import copy
import json

import httpx
import pytest

from app.generation_quality import compose_question, generation_issues, lesson_scope
from app.lesson_content import configuration_issues
from app import edumind_quiz, openai_client
from test_api import client, lesson
from test_edumind_quiz import generated_quiz
from test_assessment_grounding import grounded_plan


SCENARIO = 'A team is building a registration system. Its confirmation API fails during the Sprint.'


@pytest.mark.parametrize('stem', [
    SCENARIO + ' What should the Developers do next?',
    SCENARIO.upper() + '\n\nWhat should the Developers do next?',
    'Its confirmation API fails during the Sprint. What should the Developers do next?',
])
def test_composition_does_not_repeat_scenario_setup(stem):
    result = compose_question(SCENARIO, stem)
    assert result.casefold().count('its confirmation api fails during the sprint') == 1
    assert 'what should the developers do next?' in result.casefold()


def test_composition_keeps_distinct_context_and_the_actual_decision():
    assert compose_question(SCENARIO, 'Which plan preserves the Sprint Goal?') == SCENARIO + '\n\nWhich plan preserves the Sprint Goal?'


def test_quiz_adapter_uses_the_same_composer():
    output = generated_quiz()
    question = output['questions'][0]
    question['question'] = question['scenario'] + ' ' + question['question']
    result = edumind_quiz.adapt_questions(output, {'OBJ1': 'Requirements'}, lesson()['approved_material'])
    assert result[0]['question'].count(question['scenario']) == 1


def test_subquestions_do_not_pollute_or_get_truncated_into_the_topic():
    questions = ['Distinguish the three accountabilities.', 'Explain the artifacts.', 'Compare Review and Retrospective.']
    topic, requirements = lesson_scope('Scrum\nInstructor sub-questions to address:\n' + '\n'.join(questions), 'Respond to a Sprint risk.')
    assert topic == 'Scrum'
    assert requirements == ['Respond to a Sprint risk.', *questions]


def reviewed_plan():
    plan = grounded_plan()
    # No optional phrase examples are needed for description-based AI grading.
    def clear_examples(value):
        if isinstance(value, dict):
            if 'evidence_groups' in value:
                value['evidence_groups'] = []
            for item in value.values():
                clear_examples(item)
        elif isinstance(value, list):
            for item in value:
                clear_examples(item)
    clear_examples(plan)
    plan['generation_quality_version'] = 1
    plan['coverage_requirements'] = [
        {'id': 'REQ1', 'description': 'Distinguish accountabilities.', 'assessment_ids': ['quiz:' + plan['diagnostic_quiz'][0]['id']]},
        {'id': 'REQ2', 'description': 'Justify an adaptation.', 'assessment_ids': ['application:' + plan['application_sections'][1]['id']]},
    ]
    plan['instructor_requirements'] = [item['description'] for item in plan['coverage_requirements']]
    return plan


@pytest.mark.parametrize('change', ['missing', 'unknown_task', 'duplicate_task', 'duplicate_requirement', 'deleted_requirement'])
def test_publish_validation_rejects_incomplete_requirement_mapping(change):
    plan = reviewed_plan()
    assert not configuration_issues(plan)
    if change == 'missing': plan['coverage_requirements'][1]['assessment_ids'] = []
    if change == 'unknown_task': plan['coverage_requirements'][1]['assessment_ids'] = ['application:invented']
    if change == 'duplicate_task': plan['coverage_requirements'][1]['assessment_ids'] *= 2
    if change == 'duplicate_requirement': plan['coverage_requirements'][1]['id'] = 'REQ1'
    if change == 'deleted_requirement': plan['coverage_requirements'].pop()
    assert generation_issues(plan)
    assert configuration_issues(plan)


@pytest.mark.parametrize('examples', [
    ['Connect a decision to its effect.'],
    ['Connect a decision to its effect.', 'Explain the impact of the choice.'],
    ['The team adapts its plan.', 'THE TEAM ADAPTS ITS PLAN!'],
])
def test_copied_or_nonalternative_evidence_is_rejected(examples):
    plan = reviewed_plan()
    plan['application_rubric'][0] = {'description': 'Connect a decision to its effect.', 'evidence_groups': [examples]}
    assert any('Rubric evidence' in issue for issue in generation_issues(plan))


def test_equivalent_examples_or_no_examples_are_both_allowed():
    plan = reviewed_plan()
    plan['application_rubric'][0] = {'description': 'Connect a decision to its effect.', 'evidence_groups': [[
        'Using a local confirmation queue keeps event registration usable.',
        'We can preserve registration by saving confirmations for later delivery.',
    ]]}
    assert not generation_issues(plan)
    plan['application_rubric'][0]['evidence_groups'] = []
    assert not generation_issues(plan)


def test_older_frozen_lessons_are_not_subject_to_new_authoring_rules():
    plan = reviewed_plan()
    plan['generation_quality_version'] = 0
    plan['coverage_requirements'] = []
    assert not generation_issues(plan)


def test_authoring_preserves_every_instructor_requirement(client, monkeypatch):
    plan = lesson()
    plan['objectives'][0]['id'] = 'OBJ1'
    plan['learning_assets'][0]['objective_id'] = 'OBJ1'
    quiz = edumind_quiz.adapt_questions(generated_quiz(), {'OBJ1': 'Requirements'}, plan['approved_material'])
    monkeypatch.setattr(edumind_quiz, 'generate_quiz', lambda *args, **kwargs: quiz)
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    def provider(self, url, **kwargs):
        payload = kwargs['json']
        inputs = json.loads(payload['messages'][1]['content'])
        assert inputs['instructor_coverage_requirements'] == {'REQ1': 'Explain accountabilities.', 'REQ2': 'Compare artifacts.'}
        result = copy.deepcopy(plan)
        result['coverage_requirements'] = [
            {'id': key, 'description': 'Provider paraphrase must not replace the requirement.', 'assessment_ids': ['quiz:Q1']}
            for key in inputs['instructor_coverage_requirements']
        ]
        return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{'message': {'content': json.dumps(result)}}]})
    monkeypatch.setattr(httpx.Client, 'post', provider)
    result = openai_client.generate_learning_plan('Scrum', 'Undergraduate', approved_material=plan['approved_material'],
        objective_descriptions=[plan['objectives'][0]['description']], required_coverage=['Explain accountabilities.', 'Compare artifacts.'])
    assert result['generation_quality_version'] == 1
    assert [item['description'] for item in result['coverage_requirements']] == ['Explain accountabilities.', 'Compare artifacts.']

def mock_coverage_provider(monkeypatch,plan,mapping):
    calls=[]
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'openai')
    def provider(client,url,**kwargs):
        request=kwargs['json']
        calls.append(request)
        assert request['response_format']['json_schema']['name']=='coverage_mapping'
        inputs=json.loads(request['messages'][1]['content'])
        assert set(inputs['assessments'])=={*[f"quiz:{q['id']}" for q in plan['diagnostic_quiz']],*[f"application:{s['id']}" for s in plan['application_sections']]}
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'message':{'content':json.dumps(mapping)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    return calls


def test_coverage_only_repair_can_fix_real_references_without_rewriting_assessments(monkeypatch):
    plan=reviewed_plan()
    original=copy.deepcopy(plan)
    plan['coverage_requirements'][0]['assessment_ids']=['quiz:invented']
    plan['coverage_requirements'][1]['assessment_ids']=[]
    mapping={'REQ1':['quiz:'+plan['diagnostic_quiz'][0]['id']],'REQ2':['application:'+plan['application_sections'][1]['id']]}
    calls=mock_coverage_provider(monkeypatch,plan,mapping)
    repaired=openai_client.repair_learning_plan(plan,configuration_issues(plan))
    assert len(calls)==1
    assert not configuration_issues({**repaired,'content_approved':True})
    for key in ('diagnostic_quiz','application_sections','application_rubric','instructor_requirements','approved_material'):
        assert repaired[key]==original[key]
    assert repaired['content_approved'] is False
    assert plan['coverage_requirements'][0]['assessment_ids']==['quiz:invented']


@pytest.mark.parametrize('references',[[],['application:invented'],['quiz:Q1','quiz:Q1']])
def test_coverage_repair_cannot_approve_missing_or_fabricated_coverage(monkeypatch,references):
    plan=reviewed_plan()
    mock_coverage_provider(monkeypatch,plan,{'REQ1':references,'REQ2':['application:'+plan['application_sections'][1]['id']]})
    with pytest.raises(ValueError):openai_client.repair_coverage_requirements(plan)


def test_short_assessment_schema_limits_coverage_to_exact_task_ids(monkeypatch):
    plan=json.loads(json.dumps(reviewed_plan()).replace('"REQ"', '"OBJ1"'))
    quiz=plan['diagnostic_quiz']
    monkeypatch.setattr(edumind_quiz,'generate_quiz',lambda *a,**k:quiz)
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'openai')
    def provider(client,url,**kwargs):
        schema=kwargs['json']['response_format']['json_schema']['schema']
        assert schema['$defs']['ApplicationSection']['properties']['id']['enum']==['identify','decide','apply']
        assert set(schema['$defs']['CoverageRequirement']['properties']['assessment_ids']['items']['enum'])=={*[f"quiz:{q['id']}" for q in quiz],'application:identify','application:decide','application:apply'}
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'message':{'content':json.dumps(plan)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    result=openai_client.generate_learning_plan('Scrum','Undergraduate',approved_material=plan['approved_material'],objective_descriptions=[o['description'] for o in plan['objectives']],short_assessment=True,required_coverage=plan['instructor_requirements'])
    assert len(result['diagnostic_quiz'])==3
    assert len(result['application_sections'])==3

def test_document_preparation_repairs_coverage_before_returning_review(client,monkeypatch):
    from app import main
    plan=reviewed_plan()
    plan['coverage_requirements'][0]['assessment_ids']=['application:required_task']
    plan['coverage_requirements'][1]['assessment_ids']=[]
    monkeypatch.setattr(main,'generate_learning_plan',lambda *a,**k:copy.deepcopy(plan))
    monkeypatch.setattr(main,'discover_resources',lambda *a:[])
    monkeypatch.setattr(main,'verify_resources',lambda *a:[])
    calls=mock_coverage_provider(monkeypatch,plan,{
        'REQ1':['quiz:'+plan['diagnostic_quiz'][0]['id']],
        'REQ2':['application:'+plan['application_sections'][1]['id']],
    })
    result=main._document_plan(plan['approved_material'],'Scrum',starting_point=plan['starting_point'],ending_point=plan['ending_point'],learning_focus='Scrum',allow_course_material_fallback=True)
    assert len(calls)==1
    assert not configuration_issues({**result,'content_approved':True})
    assert result['assessment_version']==2
    assert len(result['diagnostic_quiz'])==3
    assert len(result['application_sections'])==3
