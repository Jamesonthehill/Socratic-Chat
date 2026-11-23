import asyncio
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.classifier import _classification_from_observation
from app.schemas import Source
from platform_app import engines, mission_objectives as missions, routes, socratic_setup
from platform_app.schemas import SocraticLearningStep

STEP = {'title': 'Check supplies', 'goal': 'Explain why supplies must be checked before payment.',
        'scenario': 'A customer orders a sandwich but there is no bread.',
        'question': 'Why check supplies before collecting coins?',
        'objectives': ['Explain why stock is checked before payment.', 'Explain what to do when ingredients are missing.']}
SOURCE = Source(document_id='d', chunk_id='c', title='Requirements', score=.9,
                text='Check supplies before payment. Reject an order with missing ingredients without collecting money.')
ANSWER = 'Check stock first to avoid taking money for an order we cannot make. If bread is missing, reject the order without collecting coins.'


def model(monkeypatch, awards):
    calls = []
    async def complete(_key, _url, request):
        calls.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'awards': awards})))])
    monkeypatch.setattr(missions.settings, 'llm_client_config', lambda role: ('OpenAI', 'test', 'url', 'gpt-4.1-mini'))
    monkeypatch.setattr(missions, 'socratic_chat_completion', complete)
    monkeypatch.setattr(missions, 'write_llm_request_snapshot', lambda *_: None)
    monkeypatch.setenv('SOCRATIC_EVALUATION_MODEL', 'gpt-6-luna')
    return calls


def award(index=0):
    return {'index': index, 'quote': 'Check stock first to avoid taking money for an order we cannot make.' if index == 0 else 'If bread is missing, reject the order without collecting coins.',
            'reason': 'The answer applies the objective to the unavailable sandwich.'}


def test_accumulates_exact_student_evidence_and_requests_only_unmet_objectives(monkeypatch):
    calls = model(monkeypatch, [award()]); state = {}
    asyncio.run(missions.assess_objectives(state, STEP, 0, ANSWER, STEP['question'], [SOURCE]))
    assert not missions.is_complete(state, STEP, 0)
    assert list(state['objective_progress']['0']['met']) == ['0']
    assert calls[0]['model'] == 'gpt-6-luna'
    monkeypatch.setattr(missions, 'socratic_chat_completion', mock_reply([award(1)]))
    saved = json.loads(json.dumps(state))  # What the attempt JSON round-trip preserves.
    asyncio.run(missions.assess_objectives(saved, STEP, 0, ANSWER, STEP['question'], [SOURCE]))
    assert missions.is_complete(saved, STEP, 0)
    assert state['objective_progress']['0']['met'] == {'0': award_evidence(0)}


def award_evidence(index):
    value = award(index)
    return {key: value[key] for key in ('quote', 'reason')}


def mock_reply(awards, capture=None):
    async def complete(_key, _url, request):
        if capture is not None: capture.append(json.loads(request['messages'][1]['content']))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'awards': awards})))])
    return complete


def test_no_duplicate_questions_or_evaluation_for_complete_objectives(monkeypatch):
    calls = model(monkeypatch, [award(), award(1)]); state = {}
    asyncio.run(missions.assess_objectives(state, STEP, 0, ANSWER, '', [SOURCE]))
    asyncio.run(missions.assess_objectives(state, STEP, 0, 'Okay', '', [SOURCE]))
    assert len(calls) == 1
    assert missions.is_complete(state, STEP, 0)
    assert not missions.is_complete(state, {**STEP, 'objectives': ['Explain an entirely different decision.']}, 0)
    assert not missions.is_complete(state, STEP, 1)


@pytest.mark.parametrize('bad', [
    {'index': 0, 'quote': 'A fabricated student quote about bread.', 'reason': 'Correct'},
    {'index': 99, 'quote': ANSWER, 'reason': 'Correct'},
    {'index': True, 'quote': ANSWER, 'reason': 'Correct'},
    {'index': 0, 'quote': ANSWER, 'reason': ''},
])
def test_rejects_fabricated_evidence_unknown_indices_and_empty_reasons(monkeypatch, bad):
    model(monkeypatch, [bad]); state = {}
    result = asyncio.run(missions.assess_objectives(state, STEP, 0, ANSWER, '', [SOURCE]))
    assert result['met'] == {}


def test_short_agreement_and_critical_misconception_do_not_award_progress(monkeypatch):
    calls = model(monkeypatch, [award()]); state = {}
    assert not asyncio.run(missions.assess_objectives(state, STEP, 0, 'yes', '', [SOURCE]))['met']
    result = asyncio.run(missions.assess_objectives(state, STEP, 0, ANSWER, '', [SOURCE],
                                                  SimpleNamespace(critical_misconception=True)))
    assert not result['met'] and len(calls) == 0


def test_pending_payload_excludes_met_objectives(monkeypatch):
    model(monkeypatch, []); capture=[]
    monkeypatch.setattr(missions, 'socratic_chat_completion', mock_reply([], capture))
    state={'objective_progress': {'0': {'objectives': STEP['objectives'], 'met': {'0': award_evidence(0)}}}}
    asyncio.run(missions.assess_objectives(state, STEP, 0, ANSWER, '', [SOURCE]))
    assert capture[0]['unmet_objectives'] == [{'index': 1, 'objective': STEP['objectives'][1]}]


def engine_fixture(monkeypatch, awards):
    model(monkeypatch, awards)
    async def classify(*_, **__): return _classification_from_observation(message_role='student_answer', concepts=('supplies',))
    async def none(*_, **__): return None
    monkeypatch.setattr(engines, 'classify_message', classify)
    monkeypatch.setattr(engines, 'resolve_term', none)
    monkeypatch.setattr(engines, 'assess_student_answer_qualitatively', none)
    monkeypatch.setattr(engines, '_retrieve_assignment_sources', lambda *_: [SOURCE])
    monkeypatch.setattr(engines, 'begin_trace', lambda *_a, **_k: None)
    monkeypatch.setattr(engines, 'end_trace', lambda *_: None)
    assignment = {'id': uuid4(), 'title': 'Sandwich machine', 'tool': 'socratic', 'snapshot': {
        'config': {'minimum_step_questions': 10, 'learning_steps': [deepcopy(STEP), deepcopy(STEP)]},
        'chunks': [{'document_id': 'd', 'chunk_id': 'c', 'text': SOURCE.text}]}}
    attempt = {'id': uuid4(), 'status':'in_progress', 'messages': [{'role': 'assistant', 'content': STEP['question'], 'next_thinking_step': STEP['question']}],
               'engine_state': {'socratic': {'phase': 'teaching', 'learning_step_index': 0, 'step_started_at_message_count': 1}}}
    return assignment, attempt


def test_all_objectives_met_stops_questions_before_question_minimum(monkeypatch):
    assignment, attempt = engine_fixture(monkeypatch, [award(), award(1)])
    async def forbidden(*_a, **_k): raise AssertionError('No extra question after all objectives are met')
    monkeypatch.setattr(engines.rag, 'generate_answer', forbidden)
    result = asyncio.run(engines._socratic_message(assignment, attempt, ANSWER))
    assert result['socratic']['step_readiness']['ready']
    assert missions.is_complete(result['socratic'], STEP, 0)
    assert 'Continue to the next step' in result['reply']
    assert result['socratic']['next_thinking_step'] == ''


def test_partial_progress_gives_generator_only_remaining_targets(monkeypatch):
    assignment, attempt = engine_fixture(monkeypatch, [award()]); captured=[]
    async def reply(*_a, **kwargs):
        captured.append(kwargs['active_learning_step']); return 'What should happen when bread is missing?'
    monkeypatch.setattr(engines.rag, 'generate_answer', reply)
    result = asyncio.run(engines._socratic_message(assignment, attempt, ANSWER))
    assert captured[0]['remaining_objectives'] == [STEP['objectives'][1]]
    assert captured[0]['met_objectives'] == [STEP['objectives'][0]]
    assert not result['socratic'].get('step_readiness')


def test_provider_failure_preserves_saved_progress_and_keeps_teaching(monkeypatch):
    assignment, attempt = engine_fixture(monkeypatch, [])
    attempt['engine_state']['socratic']['objective_progress'] = {'0': {'objectives': STEP['objectives'], 'met': {'0': award_evidence(0)}}}
    async def fail(*_a, **_k): raise RuntimeError('Provider unavailable')
    async def reply(*_a, **_k): return 'What should happen when bread is missing?'
    monkeypatch.setattr(missions, 'socratic_chat_completion', fail)
    monkeypatch.setattr(engines.rag, 'generate_answer', reply)
    result = asyncio.run(engines._socratic_message(assignment, attempt, ANSWER))
    assert result['socratic']['objective_progress']['0']['met'] == {'0': award_evidence(0)}
    assert not result['socratic'].get('step_readiness')


def test_next_step_server_gate_uses_objectives_not_question_count(monkeypatch):
    assignment, attempt = engine_fixture(monkeypatch, [])
    attempt['messages'].append({'role': 'user', 'content': ANSWER})
    @contextmanager
    def locked(*_): yield None, attempt
    monkeypatch.setattr(routes.store, 'locked_attempt', locked)
    monkeypatch.setattr(routes, 'get_assignment', lambda *_a, **_k: assignment)
    monkeypatch.setattr(routes.store, 'save_attempt', lambda *_: None)
    monkeypatch.setattr(routes, 'public_attempt', lambda saved: saved)
    with pytest.raises(HTTPException, match='remaining mission objectives'):
        routes.next_socratic_step(assignment['id'], {'user_id': uuid4()})
    attempt['engine_state']['socratic']['objective_progress'] = {'0': {'objectives': STEP['objectives'], 'met': {'0': award_evidence(0), '1': award_evidence(1)}}}
    result = routes.next_socratic_step(assignment['id'], {'user_id': uuid4()})
    assert result['engine_state']['socratic']['learning_step_index'] == 1
    assert not missions.is_complete(result['engine_state']['socratic'], STEP, 1)


def test_schema_accepts_legacy_steps_and_rejects_duplicate_objectives():
    assert SocraticLearningStep.model_validate({k:v for k,v in STEP.items() if k!='objectives'}).objectives == []
    with pytest.raises(ValueError, match='distinct'):
        SocraticLearningStep.model_validate({**STEP, 'objectives': [STEP['objectives'][0]]*2})


def test_generated_setup_requests_and_preserves_actionable_objectives(monkeypatch):
    passage = 'Check supplies before payment. Reject an order with missing ingredients without collecting money.'
    step = {**STEP, 'source_chunk_id':'source-1', 'evidence_quote': passage}
    payload = {'opening_prompt':'A customer orders a sandwich.', 'student_instructions':'Discuss the situation with your tutor.',
               'learning_steps':[step, {**step,'title':'Handle missing stock'}], 'source_chunk_ids':['source-1']}
    calls=[]
    async def complete(_key,_url,request):
        calls.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    monkeypatch.setattr(socratic_setup.settings,'llm_client_config',lambda _:('Ollama','test','url','test-model'))
    monkeypatch.setattr(socratic_setup,'selected_evidence',lambda _: (
        f'<file name="guide.pdf">\n[chunk_id=source-1] {passage}\n</file>', {'source-1'}, {'source-1':'guide.pdf'}))
    monkeypatch.setattr(socratic_setup,'setup_completion',complete)
    async def checks(draft,*_): return draft
    monkeypatch.setattr(socratic_setup,'add_step_checks',checks)
    result=asyncio.run(socratic_setup.generate_setup([{'id':'d','filename':'guide.pdf'}],'Sandwich machine',''))
    assert result['learning_steps'][0]['objectives']==STEP['objectives']
    schema=calls[0]['response_format']['json_schema']['schema']['properties']['learning_steps']['items']
    assert 'objectives' in schema['required']
    assert schema['properties']['objectives']['minItems']==2
    assert 'observable objectives' in calls[0]['messages'][0]['content']
