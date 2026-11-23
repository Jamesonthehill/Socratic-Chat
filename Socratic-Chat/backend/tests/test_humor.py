import asyncio
import json
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import classifier, rag
from app.answer_evaluation import should_evaluate_answer
from app.classifier import HumorObservation
from app.schemas import ChatMessage, Source
from platform_app import routes

MESSAGE = 'Just fire the developers and hire robots. Problem solved! 😂'
HUMOR = {'detected':True,'confidence':'high','evidence':MESSAGE,
         'interpretation':'Possibly playful exaggeration about replacing the team.'}


def classify(payload=None, message=MESSAGE):
    fallback=classifier._rule_classification(message,[ChatMessage(role='assistant',content='What could the team inspect?')])
    return classifier._validated_llm_classification({
        'message_role':'student_answer','target_concepts':['inspection'],'retrieval_query':'inspect the development problem',
        'retrieval_subqueries':[],'subtopic_request':False,'operational_request':'none','humor':HUMOR,
        **(payload or {}),
    },message,fallback)


def test_humor_is_a_validated_per_message_observation_not_an_assessment():
    result=classify()
    assert asdict(result.humor)==HUMOR
    assert result.message_role=='student_answer'
    assert result.assessment_candidate
    serious=replace(result,humor=HumorObservation())
    assert result.assessment_candidate==serious.assessment_candidate
    assert result.understanding_level==serious.understanding_level=='unknown'
    assert result.route==serious.route and result.conversation_action==serious.conversation_action


@pytest.mark.parametrize('humor',[
    None,{}, {'detected':True,'confidence':'high','evidence':'Words the student never said.','interpretation':'A joke.'},
    {**HUMOR,'confidence':[]},{**HUMOR,'confidence':'certain'},{**HUMOR,'detected':'true'},
    {**HUMOR,'interpretation':''},{**HUMOR,'evidence':MESSAGE*10},{**HUMOR,'detected':False},
])
def test_missing_invalid_or_fabricated_humor_cannot_change_intent(humor):
    result=classify({'humor':humor})
    assert result.message_role=='student_answer' and not result.humor.detected


def test_rule_guard_normalization_preserves_valid_humor(monkeypatch):
    result=classify({'message_role':'student_answer'},message='I am stuck 😂')
    # Use the exact latest message as evidence while the role guard normalizes support.
    result=replace(result,humor=HumorObservation(True,'medium','😂','Possibly a lighthearted expression of confusion.'))
    monkeypatch.setattr(classifier,'_classify_with_llm',AsyncMock(return_value=result))
    actual=asyncio.run(classifier.classify_message('I am stuck 😂',[]))
    assert actual.message_role=='support_request'
    assert actual.humor.detected
    assert not actual.assessment_candidate


@pytest.mark.parametrize('confidence,expected',[('high',True),('medium',True),('low',False)])
def test_generation_gets_optional_tone_data_without_extra_model_calls_or_logged_quotes(monkeypatch,confidence,expected):
    classification=replace(classify(),humor=classifier.validated_humor({**HUMOR,'confidence':confidence},MESSAGE))
    response={'lead_in':'Before replacing anyone, let’s examine the work.','next_question':'What could the team inspect to understand the difficulty?',
              'lead_emphasis':'','question_emphasis':''}
    completion=AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(response)))]))
    monkeypatch.setattr(rag,'generation_client_config',lambda:('OpenAI','test','url','gpt-6-luna'))
    monkeypatch.setattr(rag,'chat_completion',completion)
    source=Source(document_id='d',chunk_id='c',title='Scrum',text='Teams inspect progress and assumptions to identify problems before adapting their plan.',score=1)
    reply=asyncio.run(rag.generate_answer(MESSAGE,[ChatMessage(role='assistant',content='How should the team respond to difficulties?')],
        [source],classification=classification,assignment_scope=True,tutor_mode='jarvis'))
    assert '?' in reply and completion.await_count==1
    messages=completion.await_args.args[2]['messages']
    data=[m for m in messages if m['role']=='user' and '<optional_tone_observation>' in m['content']]
    assert bool(data)==expected
    system='\n'.join(m['content'] for m in messages if m['role']=='system')
    assert MESSAGE not in system
    if expected:
        assert 'Never mirror insults' in system
        assert 'deny learning credit from humor alone' in system
        assert MESSAGE in data[0]['content']
    assert messages[-2]['content']==MESSAGE  # Actual student message precedes the final style instruction.


def test_turn_metadata_saves_to_existing_attempt_json():
    attempt={'messages':[],'engine_state':{}}
    state={'socratic':{'phase':'teaching','classification':{'humor':HUMOR}},'reply':'What could the team inspect?'}
    routes.apply_state(attempt,state,MESSAGE)
    assert attempt['messages'][0]['humor']==HUMOR
    assert attempt['messages'][0]['content']==MESSAGE
    assert ChatMessage(**attempt['messages'][0]).content==MESSAGE
    # A neutral next turn has no carried-over humor observation.
    routes.apply_state(attempt,{'socratic':{'phase':'teaching','classification':{'humor':asdict(HumorObservation())}},'reply':'Tell me why.'},'Inspect the estimates.')
    assert 'humor' not in attempt['messages'][-2]


def test_classifier_schema_requests_humor_in_the_existing_single_call(monkeypatch):
    calls=[]
    async def complete(_key,_url,request):
        calls.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            'message_role':'student_answer','target_concepts':['inspection'],'retrieval_query':'inspect difficulty',
            'retrieval_subqueries':[],'subtopic_request':False,'operational_request':'none','humor':HUMOR,
        })))])
    monkeypatch.setattr(classifier,'_client_config',lambda:('OpenAI','test','url','gpt-6-luna'))
    monkeypatch.setattr(classifier,'chat_completion',complete)
    result=asyncio.run(classifier.classify_message(MESSAGE,[ChatMessage(role='assistant',content='What could the team inspect?')]))
    assert len(calls)==1 and result.humor.detected
    schema=calls[0]['response_format']['json_schema']['schema']
    assert 'humor' in schema['required']
    assert 'emoji alone does not prove humor' in calls[0]['messages'][0]['content']
