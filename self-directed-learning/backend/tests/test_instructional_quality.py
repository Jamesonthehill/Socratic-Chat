import copy
import pytest
from app import instructional_quality as quality
from app.edumind_quiz import source_passages
from test_generation_quality import reviewed_plan
from test_api import client
SOURCE='Developers inspect progress toward the Sprint Goal and adapt the Sprint Backlog. The Sprint Review inspects product outcomes with stakeholders. The Retrospective improves how the team works. A usable Increment meets the Definition of Done, while acceptance criteria describe an individual item.'

def plan():
    p=reviewed_plan();p.update(instructional_quality_version=1,approved_material=SOURCE)
    original=p['objectives'][0]
    p['objectives']=[{**copy.deepcopy(original),'id':f'OBJ{i+1}','description':description} for i,description in enumerate(['Explain accountabilities','Distinguish events and artifacts','Apply adaptation and quality'])]
    original_asset=p['learning_assets'][0]
    p['learning_assets']=[{**copy.deepcopy(original_asset),'objective_id':f'OBJ{i+1}'} for i in range(3)]
    for i,q in enumerate(p['diagnostic_quiz']):
        q['objective_id']=f'OBJ{i+1}';q['material_reference']='S1: '+source_passages(SOURCE)['S1']
    for i,s in enumerate(p['application_sections']):s['objective_ids']=[f'OBJ{i+1}']
    return p

def passing_review(p):
    result={field:True for field in ('distinct_quiz_coverage','source_relevance','no_duplicate_questions','progressive_application','rubric_alignment','assessment_complete','interview_design','prerequisite_alignment','quiz_progression','assessable_rubrics','factual_support')}
    result.update(requirements=[{'requirement_id':f'REQ{i+1}','study_supported':True,'assessment_supported':True,'source_supported':True,'explanation':'The explanation and assessment explicitly elicit this reasoning.'} for i,_ in enumerate(p['instructor_requirements'])],issues=[])
    return result

def test_source_wrappers_do_not_become_teaching_evidence():
    assert quality.clean_source('Page 1: Document:\n\n'+SOURCE)==SOURCE
    assert quality.clean_source('Page 1: Document: '+SOURCE)==SOURCE
    assert source_passages('Page 1: Document:\n\n'+SOURCE)['S1']==SOURCE
    assert not quality.meaningful('Page 1: Document:')

def objective_design():
    return {'objectives':{'OBJ1':'Explain the team accountabilities.','OBJ2':'Distinguish the Scrum events.','OBJ3':'Relate artifacts and commitments.'},
            'requirement_objectives':{'REQ1':['OBJ1'],'REQ2':['OBJ2'],'REQ3':['OBJ3']}}


def test_objective_design_preserves_all_requirements(monkeypatch):
    calls=[]
    def provider(name,schema,instructions,data):
        calls.append(name)
        assert data['source']==SOURCE
        assert set(schema['properties']['requirement_objectives']['properties'])=={'REQ1','REQ2','REQ3'}
        return objective_design()
    monkeypatch.setattr(quality,'authoring_json',provider)
    assert len(set(quality.design_objectives(SOURCE,'Scrum',['Accountabilities','Events','Artifacts'])))==3
    assert calls==['objective_design']


def test_objective_design_repairs_a_missing_broad_end_goal(monkeypatch):
    broken=objective_design();broken['requirement_objectives'].pop('REQ1')
    repaired=objective_design();repaired['requirement_objectives']['REQ1']=['OBJ1','OBJ2','OBJ3']
    calls=[]
    def provider(name,schema,instructions,data):
        calls.append(name)
        if len(calls)==1:return broken
        assert data['requirements']['REQ1']=='Participate effectively in a complete Sprint.'
        assert data['repair_issues']
        return repaired
    monkeypatch.setattr(quality,'authoring_json',provider)
    assert len(quality.design_objectives(SOURCE,'Scrum',['Participate effectively in a complete Sprint.','Events','Artifacts']))==3
    assert calls==['objective_design','objective_design_repair']


def test_objective_design_cannot_silently_drop_a_requirement(monkeypatch):
    broken=objective_design();broken['requirement_objectives'].pop('REQ2')
    calls=[]
    def provider(*args):calls.append(args);return broken
    monkeypatch.setattr(quality,'authoring_json',provider)
    with pytest.raises(ValueError,match='one automatic repair'):
        quality.design_objectives(SOURCE,'Scrum',['Roles','Events','Artifacts'])
    assert len(calls)==2


@pytest.mark.parametrize('defect',['duplicate_description','unknown_objective','empty_allocation','missing_group'])
def test_objective_repair_retains_validation(monkeypatch,defect):
    broken=objective_design()
    if defect=='duplicate_description':broken['objectives']['OBJ2']=broken['objectives']['OBJ1']
    if defect=='unknown_objective':broken['requirement_objectives']['REQ1']=['invented']
    if defect=='empty_allocation':broken['requirement_objectives']['REQ1']=[]
    if defect=='missing_group':broken['objectives'].pop('OBJ3')
    monkeypatch.setattr(quality,'authoring_json',lambda *a:broken)
    with pytest.raises(ValueError):quality.design_objectives(SOURCE,'Scrum',['Roles','Events','Artifacts'])


@pytest.mark.parametrize('check',['distinct_quiz_coverage','source_relevance','no_duplicate_questions','progressive_application','rubric_alignment','assessment_complete','interview_design','prerequisite_alignment','quiz_progression','assessable_rubrics','factual_support'])
def test_independent_review_rejects_each_failure(monkeypatch,check):
    p=plan();report=passing_review(p);report[check]=False
    monkeypatch.setattr(quality,'authoring_json',lambda *a:report)
    with pytest.raises(ValueError,match='Revise the lesson'):quality.review_plan(p)
    assert 'instructional_review' not in p

def test_labels_are_not_coverage_evidence(monkeypatch):
    p=plan();report=passing_review(p);report['requirements'][0]['assessment_supported']=False
    report['requirements'][0]['explanation']='The task only mentions the topic; it never asks for the required reasoning.'
    monkeypatch.setattr(quality,'authoring_json',lambda *a:report)
    with pytest.raises(ValueError,match='never asks'):quality.review_plan(p)

def test_review_fingerprint_and_forced_publish(monkeypatch):
    p=plan();calls=[]
    def review(*args):calls.append(args);return passing_review(p)
    monkeypatch.setattr(quality,'authoring_json',review)
    checked=quality.review_plan(p);quality.review_plan(checked)
    assert len(calls)==1
    edited=copy.deepcopy(checked);edited['application_sections'][1]['prompt']='Using the issue you identified, decide which plan to change.'
    quality.review_plan(edited);assert len(calls)==2
    quality.review_plan(checked,force=True);assert len(calls)==3

@pytest.mark.parametrize('change',['single_objective','fabricated_source','empty_source','duplicate_prompt','invalid_stage_mapping'])
def test_structural_checks_block_known_bad_patterns(change):
    p=plan()
    if change=='single_objective':
        for q in p['diagnostic_quiz']:q['objective_id']='OBJ1'
    if change=='fabricated_source':p['diagnostic_quiz'][0]['material_reference']='S1: Page 1: Document:'
    if change=='empty_source':p['approved_material']='Page 1: Document:'
    if change=='duplicate_prompt':p['application_sections'][1]['prompt']=p['application_sections'][0]['prompt']
    if change=='invalid_stage_mapping':
        p['application_sections'][0]['objective_ids']=['invented']
    assert quality.structural_issues(p)

def test_legacy_lessons_keep_their_existing_behavior():
    p=reviewed_plan();assert quality.review_plan(p) is p

def test_prepare_separates_source_from_guidance(client,monkeypatch):
    from app import main
    captured={}
    def prepare(material,filename,**kwargs):captured.update(material=material,**kwargs);return plan()
    monkeypatch.setattr(main,'_document_plan',prepare)
    monkeypatch.setattr(quality,'authoring_json',lambda *a:passing_review(plan()))
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','quality-test')
    r=client.post('/internal/platform/lessons/prepare',headers={'X-Platform-Service':'quality-test'},json={'material':SOURCE,'filename':'Scrum.pdf','focus':'Teach Scrum','starting_point':'Basic development','ending_point':'Apply Scrum','instructional_quality':True})
    assert r.status_code==200,r.text
    assert captured['material']==SOURCE
    assert captured['instructional_quality'] is True
    assert r.json()['instructional_review']['passed']

def test_publication_review_blocks_writes_even_with_a_claimed_pass(client,monkeypatch):
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','quality-test')
    p=plan();p['instructional_review']={'passed':True,'fingerprint':quality.fingerprint(p)}
    report=passing_review(p);report['rubric_alignment']=False
    monkeypatch.setattr(quality,'authoring_json',lambda *a:report)
    r=client.post('/internal/platform/lessons/publish',headers={'X-Platform-Service':'quality-test'},json={'id':'quality-test','title':'Scrum','instructor':{'id':'teacher','email':'teacher@example.invalid','display_name':'Teacher'},'students':[],'learning_plan':p})
    assert r.status_code==422,r.text
    assert 'rubric alignment' in str(r.json())

def test_failed_review_returns_an_editable_draft_without_approving_it(client,monkeypatch):
    from app import main
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','quality-test')
    monkeypatch.setattr(main,'_document_plan',lambda *a,**k:plan())
    report=passing_review(plan());report['progressive_application']=False
    monkeypatch.setattr(quality,'authoring_json',lambda *a:report)
    r=client.post('/internal/platform/lessons/prepare',headers={'X-Platform-Service':'quality-test'},json={'material':SOURCE,'filename':'Scrum.pdf','focus':'Scrum','starting_point':'Programming','ending_point':'Apply Scrum','instructional_quality':True})
    assert r.status_code==200,r.text
    assert r.json()['instructional_review']['passed'] is False
    assert r.json()['instructional_review']['issues']
    assert len(r.json()['application_sections'])==3

def test_coverage_is_collective_not_every_objective_in_every_stage():
    from app.lesson_content import configuration_issues
    p=plan()
    for section in p['application_sections']:section['objective_ids']=['OBJ3']
    # The application can focus on transfer; the distinct quiz still assesses all groups.
    assert not configuration_issues({**p,'content_approved':True})
    assert not quality.structural_issues(p)
    p['diagnostic_quiz'][0]['objective_id']='OBJ3'
    assert configuration_issues({**p,'content_approved':True})


def test_optional_examples_are_normalized_without_rewriting_criteria():
    p=plan()
    p['application_rubric']=[{'description':'Explain why the approach protects the goal.','evidence_groups':[['Protects the goal'],['Explain why the approach protects the goal.','Another example'],['The team limits scope to preserve the goal.','The team delays unrelated work to keep its goal attainable.']]}]
    original=copy.deepcopy(p)
    normalized,count=quality.normalize_optional_rubric_examples(p)
    assert count==2
    assert normalized['application_rubric'][0]['description']==original['application_rubric'][0]['description']
    assert normalized['application_rubric'][0]['evidence_groups']==[original['application_rubric'][0]['evidence_groups'][2]]
    assert p==original


def test_configuration_failures_return_an_editable_draft_without_extra_calls(client,monkeypatch):
    from app import main
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','quality-test')
    broken=plan();broken['application_sections'][1]['objective_ids']=['invalid']
    monkeypatch.setattr(main,'_document_plan',lambda *a,**k:broken)
    monkeypatch.setattr(quality,'authoring_json',lambda *a:pytest.fail('Do not run semantic review before fixing configuration issues'))
    r=client.post('/internal/platform/lessons/prepare',headers={'X-Platform-Service':'quality-test'},json={'material':SOURCE,'filename':'Scrum.pdf','focus':'Scrum','starting_point':'Programming','ending_point':'Apply Scrum','instructional_quality':True})
    assert r.status_code==200,r.text
    assert r.json()['instructional_review']['passed'] is False
    assert any('valid' in issue for issue in r.json()['instructional_review']['issues'])
    assert r.json()['application_sections']==broken['application_sections']
    published=client.post('/internal/platform/lessons/publish',headers={'X-Platform-Service':'quality-test'},json={'id':'blocked-draft','title':'Scrum','instructor':{'id':'teacher','email':'teacher@example.invalid','display_name':'Teacher'},'students':[],'learning_plan':r.json()})
    assert published.status_code==422


def test_actual_preparation_does_not_discard_draft_for_optional_examples(client,monkeypatch):
    from app import main
    p=plan()
    p['application_rubric'][0]['evidence_groups']=[['A single optional phrase']]
    monkeypatch.setattr(quality,'design_objectives',lambda *a:[o['description'] for o in p['objectives']])
    monkeypatch.setattr(main,'generate_learning_plan',lambda *a,**k:copy.deepcopy(p))
    monkeypatch.setattr(main,'repair_learning_plan',lambda *a:pytest.fail('Do not call the legacy repair pipeline for quality-mode drafts'))
    monkeypatch.setattr(main,'discover_resources',lambda *a:[])
    monkeypatch.setattr(main,'verify_resources',lambda *a:[])
    result=main._document_plan(SOURCE,'Scrum.pdf',starting_point='Basic programming',ending_point='Apply Scrum',learning_focus='Scrum',allow_course_material_fallback=True,instructional_quality=True)
    assert result['application_rubric'][0]['description']==p['application_rubric'][0]['description']
    assert result['application_rubric'][0]['evidence_groups']==[]
    assert result['instructional_review']['notes']
    assert len(result['diagnostic_quiz'])==3
    assert len(result['application_sections'])==3


@pytest.mark.parametrize('topic,source', [
    ('Scrum', SOURCE),
    ('Ecology', 'Energy flows through food webs from producers to consumers. Removing a predator can increase herbivores and reduce plant biomass. Nutrient cycles depend on decomposers returning matter to the ecosystem.')])
def test_scoped_repair_revalidates_and_preserves_instructor_inputs(monkeypatch, topic, source):
    p=plan();p['topic']=topic;p['approved_material']=source
    from app.schemas import LearningPlan
    p=LearningPlan.model_validate(p).model_dump()
    for q in p['diagnostic_quiz']:q['material_reference']='S1: '+source
    target='application_sections:'+p['application_sections'][0]['id']
    calls=[]
    def provider(name,schema,instructions,data):
        calls.append(name)
        if name=='instructional_repair':
            assert set(schema['properties'])=={target}
            assert data['lesson']['prerequisite_knowledge']==p['prerequisite_knowledge']
            section=copy.deepcopy(p['application_sections'][0])
            section['prompt']='Given the supplied hypothetical scenario, identify the central issue and explain which scenario evidence supports it.'
            return {target:section}
        report=passing_review(p)
        if len(calls)==1:
            report.update(prerequisite_alignment=False,repair_targets=[target],issues=['This prompt requires prior personal project experience absent from the prerequisites.'])
        else:
            assert data['lesson']['application_sections'][0]['prompt']!=p['application_sections'][0]['prompt']
        return report
    monkeypatch.setattr(quality,'authoring_json',provider)
    result=quality.review_and_repair(p)
    assert calls==['instructional_review','instructional_repair','instructional_review']
    assert result['instructional_review']['passed']
    assert result['diagnostic_quiz']==p['diagnostic_quiz']
    assert result['instructor_requirements']==p['instructor_requirements']
    assert not result['content_approved']


def test_repair_is_bounded_and_unresolved_failures_never_pass(monkeypatch):
    p=plan();calls=[];target='application_rubric'
    def provider(name,*args):
        calls.append(name)
        if name=='instructional_repair':return {target:p[target]}
        result=passing_review(p)
        result.update(assessable_rubrics=False,repair_targets=[target],issues=['Criterion rewards generic collaboration without observable subject reasoning.'])
        return result
    monkeypatch.setattr(quality,'authoring_json',provider)
    with pytest.raises(ValueError,match='observable subject reasoning'):quality.review_and_repair(p)
    assert calls==['instructional_review','instructional_repair','instructional_review']
    assert 'instructional_review' not in p


@pytest.mark.parametrize('target',['prerequisite_knowledge','approved_material','objectives','invented'])
def test_reviewer_cannot_repair_instructor_constraints(monkeypatch,target):
    p=plan();calls=[]
    def provider(name,*args):
        calls.append(name);report=passing_review(p)
        report.update(prerequisite_alignment=False,repair_targets=[target])
        return report
    monkeypatch.setattr(quality,'authoring_json',provider)
    with pytest.raises(ValueError):quality.review_and_repair(p)
    assert calls==['instructional_review']


def test_new_review_does_not_trust_an_older_cached_pass(monkeypatch):
    p=plan();p['instructional_review']={'passed':True,'fingerprint':quality.fingerprint(p)}
    calls=[]
    monkeypatch.setattr(quality,'authoring_json',lambda *a:(calls.append(a) or passing_review(p)))
    assert quality.review_plan(p)['instructional_review']['review_version']==2
    assert len(calls)==1
