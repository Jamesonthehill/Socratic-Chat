"""Evaluation harness tests are offline: model/network calls are injected doubles."""
import copy
import json

import httpx
import pytest

from evaluation import runner as ev
from test_generation_quality import reviewed_plan


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args,**kwargs):
        pytest.fail('Evaluation unit tests must never make network calls.')
    monkeypatch.setattr(httpx.Client,'send',fail)


def output():
    p=reviewed_plan()
    from app.edumind_quiz import source_passages
    source=p['approved_material']
    sid,text=next(iter(source_passages(source).items()))
    for q in p['diagnostic_quiz']: q['material_reference']=sid+': '+text
    p['study_resources']=[];p['prerequisite_resources']=[]
    return {'lesson':p,'error':None,'approved_urls':[],'generation_latency_seconds':0}


def case_for(p):
    _,cases=ev.load_cases()
    c=copy.deepcopy(cases[0]);c['source']=p['approved_material']
    return c


def verdict(p, score=3):
    lesson_quote=p['diagnostic_quiz'][0]['question']
    source_quote=p['approved_material'][:30]
    return dict(scores={dim:dict(score=score,explanation='The observed task and source demonstrate the requested reasoning.',lesson_quote=lesson_quote,source_quote=source_quote) for dim in ev.DIMENSIONS},
                expected_behavior_met=True,behavior_explanation='The lesson asks for the intended observable reasoning.',
                behavior_quote=lesson_quote,behavior_source_quote=source_quote,
                quiz_audit={q['id']:dict(unique_defensible_key=True,plausible_distractors=True,option_indices=[q['correct_index']],explanation='Only the keyed option satisfies the scenario constraints.') for q in p['diagnostic_quiz']},
                task_audit=dict(prerequisite_aligned=True,sufficient_scenario=True,distinct_reasoning_steps=True,lesson_quote=lesson_quote,explanation='The hypothetical task asks for distinct evidence-based decisions.'),
                outcome_audit={f'R{i+1}':dict(assessed=True,assessment_ids=['quiz:'+p['diagnostic_quiz'][0]['id']],explanation='The actual question elicits the requested competency.') for i in range(3)},failures=[])


def test_dataset_has_all_domains_and_negative_cases_and_stable_hashes():
    _,cases=ev.load_cases();_,again=ev.load_cases()
    assert 10<=len(cases)<=15
    assert {'scrum','git','sql','rest','testing','probability','biology','physics','economics','cybersecurity'} <= {c['id'] for c in cases}
    assert {c['expected_behavior'] for c in cases}=={'lesson','flag_constraint_conflict','flag_insufficient_evidence'}
    assert [c['input_hash'] for c in cases]==[c['input_hash'] for c in again]
    assert all(c['review_status']=='candidate' for c in cases)


def test_freeze_records_review_attestation_and_hashes(tmp_path):
    manifest=ev.freeze(ev.ROOT/'cases.json',tmp_path/'frozen.json','Subject reviewer')
    assert len(manifest['cases'])==len(ev.load_cases()[1])
    assert manifest['reviewed_by']=='Subject reviewer'
    with pytest.raises(ValueError): ev.freeze(ev.ROOT/'cases.json',tmp_path/'bad.json','')


@pytest.mark.parametrize('mutation,expected',[
    ('duplicate_application','duplicates'),('malformed_evidence','malformed optional'),
    ('unsupported_citation','citation is not'),
])
def test_adversarial_deterministic_failures(mutation,expected):
    original=output();updated=ev.challenge_output(original,mutation)
    failures=ev.deterministic_checks(updated['lesson'],original['lesson']['approved_material'],set())
    assert any(expected in f for f in failures)
    assert updated!=original


@pytest.mark.parametrize('change,expected',[
    ('schema','Schema invalid'),('objective','invalid objective'),('count','three ordered'),
    ('url','Invented or unapproved'),('options','answer options'),('field','missing required'),
])
def test_independent_checks_do_not_depend_on_production_review(change,expected):
    p=output()['lesson']
    p['instructional_review']={'passed':True,'checks':{'everything':'excellent'}}
    if change=='schema': del p['title']
    if change=='objective': p['diagnostic_quiz'][0]['objective_id']='unknown'
    if change=='count': p['diagnostic_quiz'].pop()
    if change=='url': p['study_resources']=[dict(title='Invented',url='https://example.invalid/not-a-reading',provider='Unknown')]
    if change=='options': p['diagnostic_quiz'][0]['options'][1]=p['diagnostic_quiz'][0]['options'][0]
    if change=='field': p['diagnostic_quiz'][0]['explanation']=''
    assert any(expected in f for f in ev.deterministic_checks(p,p.get('approved_material',''),set()))


def test_reading_urls_require_both_provenance_and_reachability():
    p=output()['lesson'];url='https://example.org/approved'
    p['study_resources']=[dict(title='Approved',url=url,provider='Instructor')]
    assert any('unverified' in f for f in ev.deterministic_checks(p,p['approved_material'],{url}))
    assert any('failed reachability' in f for f in ev.deterministic_checks(p,p['approved_material'],{url},lambda u:False))
    assert not any('URL' in f for f in ev.deterministic_checks(p,p['approved_material'],{url},lambda u:True))


@pytest.mark.parametrize('dimension',ev.DIMENSIONS)
def test_independent_judge_uses_own_rubric_and_actual_evidence(monkeypatch,dimension):
    from app import instructional_quality
    outcome=output();p=outcome['lesson'];p['instructional_review']={'passed':True}
    report=verdict(p);report['scores'][dimension]['score']=1
    def evaluator(name,schema,instructions,data):
        assert name=='independent_sdl_evaluation'
        assert 'instructional_review' not in data['observed']['lesson']
        assert 'coverage_requirements' not in data['observed']['lesson']
        assert 'ending_point' not in data['observed']['lesson']
        assert 'source' not in data['instructor_case']
        assert all(ev.quote_present(data['source_text'],q) for q in schema['properties']['behavior_source_quote']['enum'])
        assert set(schema['properties']['scores']['properties'])==set(ev.DIMENSIONS)
        assert len(data['rubric']['dimensions'][dimension])==4
        return report
    monkeypatch.setattr(instructional_quality,'authoring_json',evaluator)
    result=ev.judge(case_for(p),outcome)
    assert result['scores'][dimension]['score']==1


@pytest.mark.parametrize('defect',['missing_dimension','invented_source','invented_lesson','string_score'])
def test_bad_evaluator_responses_cannot_pass(monkeypatch,defect):
    from app import instructional_quality
    outcome=output();p=outcome['lesson'];report=verdict(p)
    if defect=='missing_dimension': del report['scores']['accuracy']
    if defect=='invented_source': report['scores']['accuracy']['source_quote']='Fabricated evidence not in source'
    if defect=='invented_lesson': report['scores']['accuracy']['lesson_quote']='Fabricated evidence not in lesson'
    if defect=='string_score': report['scores']['accuracy']['score']='3'
    monkeypatch.setattr(instructional_quality,'authoring_json',lambda *a:report)
    with pytest.raises(ValueError): ev.judge(case_for(p),outcome)


def test_invalid_judge_response_is_saved_for_audit(tmp_path,monkeypatch):
    from app import instructional_quality
    outcome=output();report=verdict(outcome['lesson'])
    report['behavior_source_quote']='This evidence was invented by the evaluator.'
    monkeypatch.setattr(instructional_quality,'authoring_json',lambda *a:report)
    audit=tmp_path/'judge-response.json'
    with pytest.raises(ValueError): ev.judge(case_for(outcome['lesson']),outcome,audit)
    assert json.loads(audit.read_text(encoding='utf-8'))==report


@pytest.mark.parametrize('defect',['weak_options','ambiguous_key','prerequisite','coverage'])
def test_explicit_audits_block_false_passes_even_with_perfect_scores(monkeypatch,defect):
    from app import instructional_quality
    outcome=output();p=outcome['lesson'];report=verdict(p)
    qid=p['diagnostic_quiz'][0]['id']
    if defect=='weak_options': report['quiz_audit'][qid]['plausible_distractors']=False
    if defect=='ambiguous_key': report['quiz_audit'][qid]['unique_defensible_key']=False
    if defect=='prerequisite': report['task_audit']['prerequisite_aligned']=False
    if defect=='coverage': report['outcome_audit']['R3']['assessed']=False
    monkeypatch.setattr(instructional_quality,'authoring_json',lambda *a:report)
    checked=ev.judge(case_for(p),outcome)
    assert checked['failures']
    assert all(s['score']==3 for s in checked['scores'].values())


def test_negative_cases_require_specific_observed_evidence(monkeypatch):
    from app import instructional_quality
    _,cases=ev.load_cases();case=next(c for c in cases if c['id']=='sql-missing-evidence')
    report=verdict(output()['lesson']);report.update(scores={},quiz_audit={},task_audit=None,outcome_audit={})
    report.update(behavior_quote='The selected source does not teach joins or aggregation.',behavior_source_quote='These notes do not explain joins, grouping, aggregates or NULL behavior.')
    monkeypatch.setattr(instructional_quality,'authoring_json',lambda *a:report)
    assert ev.judge(case,{'lesson':None,'error':report['behavior_quote']})['expected_behavior_met']
    with pytest.raises(ValueError): ev.judge(case,{'lesson':None,'error':'Provider unavailable'})


def test_generation_calls_real_prepare_contract_without_publishing(monkeypatch):
    from app import platform_lessons,main
    _,cases=ev.load_cases();captured={}
    def prepare(body):
        captured.update(body.model_dump());main.verify_resources([],body.focus)
        return output()['lesson']
    monkeypatch.setattr(platform_lessons,'prepare',prepare)
    monkeypatch.setattr(main,'verify_resources',lambda *a:[{'url':'https://example.org/verified'}])
    result=ev.generate(cases[0])
    assert captured['instructional_quality'] is True
    assert captured['material']==cases[0]['source']
    assert captured['starting_point']==cases[0]['prerequisite_knowledge']
    assert cases[0]['specific_concepts'][0] in captured['focus']
    assert result['approved_urls']==['https://example.org/verified']


def test_baseline_deltas_and_changed_inputs_are_not_comparable():
    p=output()['lesson'];old={'id':'scrum','input_hash':'a','passed':True,'judge':verdict(p)}
    new=copy.deepcopy(old);new['passed']=False;new['judge']['scores']['coverage']['score']=1
    result=ev.compare([new],{'protocol_hash':'p','results':[old]},'p')[0]
    assert result['new_regression'] and result['score_deltas']['coverage']==-2
    new['input_hash']='b'
    assert not ev.compare([new],{'protocol_hash':'p','results':[old]},'p')[0]['comparable']
    assert not ev.compare([old],{'protocol_hash':'other','results':[old]},'p')[0]['comparable']


def test_offline_replay_saves_report_and_cannot_claim_a_quality_pass(tmp_path):
    _,cases=ev.load_cases();case=cases[0];prior=tmp_path/'prior';destination=tmp_path/'run'
    ev.write_json(prior/'scrum'/'output.json',{'input_hash':case['input_hash'],'outcome':output()})
    assert ev.main(['--case','scrum','--replay',str(prior),'--output',str(destination),'--allow-candidates'])==1
    report=json.loads((destination/'report.json').read_text(encoding='utf-8'))
    assert report['results'][0]['judge'] is None
    assert report['results'][0]['status']=='not_evaluated'
    assert report['aggregate']['passed']==0
    assert (destination/'report.md').exists()


def test_live_calls_require_explicit_opt_in():
    with pytest.raises(SystemExit): ev.main(['--case','scrum','--allow-candidates'])


@pytest.mark.parametrize('score,expected_status',[(3,'pass'),(2,'fail'),(1,'fail')])
def test_cli_quality_gate_uses_independent_scores_not_production_pass(tmp_path,monkeypatch,score,expected_status):
    from app import openai_client as ai
    outcome=output();outcome['lesson']['instructional_review']={'passed':True}
    monkeypatch.setattr(ai,'runtime_ai_mode',lambda:'openai')
    monkeypatch.setattr(ev,'generate',lambda case:outcome)
    monkeypatch.setattr(ev,'deterministic_checks',lambda *args:[])
    monkeypatch.setattr(ev,'judge',lambda *args:verdict(outcome['lesson'],score))
    destination=tmp_path/'run'
    ev.main(['--case','scrum','--live','--allow-candidates','--output',str(destination)])
    report=json.loads((destination/'report.json').read_text(encoding='utf-8'))
    assert report['results'][0]['status']==expected_status
    assert report['aggregate']['dimensions']['coverage']['n']==1


def test_stale_freeze_manifest_blocks_live_calls(tmp_path):
    manifest=ev.freeze(ev.ROOT/'cases.json',tmp_path/'frozen.json','Reviewer')
    manifest['cases']['scrum']='changed'
    ev.write_json(tmp_path/'frozen.json',manifest)
    with pytest.raises(SystemExit):
        ev.main(['--case','scrum','--live','--manifest',str(tmp_path/'frozen.json')])


def test_all_challenges_are_isolated_from_original_output():
    original=output()
    for name in ev.CHALLENGES:
        assert ev.challenge_output(original,name)!=original
    assert original==output()


def test_actual_study_guide_fixture_has_document_provenance():
    import hashlib
    _,cases=ev.load_cases()
    case=next(c for c in cases if c['id']=='scrum-study-guide')
    metadata=json.loads((ev.ROOT/'sources/scrum-study-guide.provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(case['source'].encode()).hexdigest()==metadata['fixture_sha256']
    assert metadata['source_pages']==14 and metadata['selected_pages']==[2,4,5,6,7,10,11,12,13]
    assert 15000<len(case['source'])<=30000


def test_evaluator_schema_builds_when_launched_by_runpy():
    import runpy
    namespace=runpy.run_path(str(ev.ROOT/'runner.py'),run_name='sdl_schema_check')
    assert 'DimensionScore' in namespace['JudgeReport'].model_json_schema()['$defs']


def test_quote_candidates_are_verbatim_and_whitespace_is_the_only_tolerance():
    source='First source sentence.\nSecond supported claim.'
    assert all(ev.quote_present(source,q) for q in ev.quote_candidates(source))
    assert ev.quote_present(source,'First source sentence. Second supported claim.')
    assert not ev.quote_present(source,'First source sentence. Invented supported claim.')


def test_missing_coverage_challenge_removes_shared_task_escape_route():
    original=output()
    original['lesson']['required_task']['submission_prompt']='Explain the last objective using TARGET_ONLY.'
    challenged=ev.challenge_output(original,'missing_coverage')
    assert 'TARGET_ONLY' not in json.dumps(challenged['lesson']['required_task'])
    assert 'TARGET_ONLY' in original['lesson']['required_task']['submission_prompt']


def test_explicit_env_file_overrides_stale_provider_only(tmp_path,monkeypatch,capsys):
    import os
    config=tmp_path/'.env'
    config.write_text('OPENAI_API_KEY=test-placeholder\nDATABASE_URL=do-not-import\n',encoding='utf-8')
    monkeypatch.setenv('OPENAI_API_KEY','stale-placeholder')
    monkeypatch.setenv('DATABASE_URL','preserve-existing')
    assert ev.main(['--env-file',str(config),'--list'])==0
    assert os.environ['OPENAI_API_KEY']=='test-placeholder'
    assert os.environ['DATABASE_URL']=='preserve-existing'
    assert 'test-placeholder' not in capsys.readouterr().out


def test_usage_trace_records_tokens_latency_and_optional_cost_without_secrets(monkeypatch):
    def send(client,request,*args,**kwargs):
        return httpx.Response(200,json={'model':'fixed','usage':{'prompt_tokens':100,'completion_tokens':50}},request=request)
    monkeypatch.setattr(httpx.Client,'send',send)
    with ev.usage_trace({'fixed':{'input_per_million':1,'output_per_million':2}}) as calls:
        with httpx.Client() as client:
            client.post('https://example.org/chat/completions',headers={'Authorization':'secret'},json={'model':'fixed','messages':['private material']})
    assert calls[0]['estimated_cost_usd']==0.0002
    assert calls[0]['latency_seconds']>=0
    assert 'secret' not in json.dumps(calls) and 'private material' not in json.dumps(calls)
