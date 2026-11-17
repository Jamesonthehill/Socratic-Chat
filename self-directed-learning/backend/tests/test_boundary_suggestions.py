"""Boundary suggestions are explicit, validated drafts, never lesson generation."""
import json
from types import SimpleNamespace
import pytest
from test_api import client, lesson


@pytest.mark.parametrize('provided', [{}, {'starting_point':'Author-provided prerequisites'}, {'ending_point':'Author-provided outcome'}])
def test_suggestions_preserve_supplied_values_and_use_private_preferences(monkeypatch, provided):
    from app import openai_client as ai
    seen = {}
    monkeypatch.setattr(ai, 'runtime_ai_mode', lambda:'openai')
    monkeypatch.setattr(ai, '_chat_settings', lambda:('https://example.invalid','model',{}))
    def post(*args, **kwargs):
        seen.update(kwargs['json'])
        return SimpleNamespace(raise_for_status=lambda:None, json=lambda:{'choices':[{'message':{'content':json.dumps({'starting_point':'Basic teamwork','ending_point':'Apply Scrum'})}}]})
    monkeypatch.setattr(ai, '_post_authoring_request', post)
    context={'focus':'Scrum','material':'Course text','additional_instructions':'Use a campus project.',**provided}
    result=ai.suggest_learning_boundaries(context)
    for key,value in provided.items(): assert result[key] == value
    assert set(result)=={'starting_point','ending_point'}
    request=json.loads(seen['messages'][1]['content'])
    assert request['additional_instructions']=='Use a campus project.'
    assert request['material']=='Course text'


@pytest.mark.parametrize('payload', ['{}','null','{"starting_point":"","ending_point":"Apply Scrum"}'])
def test_invalid_suggestions_cannot_be_confirmed(monkeypatch,payload):
    from app import openai_client as ai
    monkeypatch.setattr(ai,'runtime_ai_mode',lambda:'openai')
    monkeypatch.setattr(ai,'_chat_settings',lambda:('https://example.invalid','model',{}))
    monkeypatch.setattr(ai,'_post_authoring_request',lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'choices':[{'message':{'content':payload}}]}))
    with pytest.raises(ValueError,match='incomplete lesson details'):
        ai.suggest_learning_boundaries({'starting_point':'','ending_point':''})


def test_suggestion_endpoint_does_not_generate_a_lesson(client,monkeypatch):
    from app import openai_client as ai
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','boundaries-test')
    seen={}
    def suggest(context):
        seen.update(context)
        return {'starting_point':'Basic teamwork','ending_point':'Apply Scrum'}
    monkeypatch.setattr(ai,'suggest_learning_boundaries',suggest)
    monkeypatch.setattr(ai,'generate_learning_plan',lambda *a,**k:pytest.fail('Suggestions must not generate lessons'))
    result=client.post('/internal/platform/lessons/suggest-boundaries',headers={'X-Platform-Service':'boundaries-test'},json={'filename':'Scrum','material':'A Scrum team inspects progress toward its Sprint Goal.','focus':'Scrum','additional_instructions':'Use campus examples.'})
    assert result.status_code==200,result.text
    assert result.json()=={'starting_point':'Basic teamwork','ending_point':'Apply Scrum'}
    assert seen['additional_instructions']=='Use campus examples.'


def test_private_preferences_are_not_added_to_approved_material(client,monkeypatch):
    from app import main
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','boundaries-test')
    monkeypatch.setattr(main,'discover_resources',lambda *a:[])
    monkeypatch.setattr(main,'verify_resources',lambda *a:[])
    captured={}
    def generate(*a,**kwargs):
        captured.update(kwargs)
        return lesson()
    monkeypatch.setattr(main,'generate_learning_plan',generate)
    result=client.post('/internal/platform/lessons/prepare',headers={'X-Platform-Service':'boundaries-test'},json={'filename':'Scrum','material':lesson()['approved_material'],'focus':'Scrum','starting_point':'Basic teamwork','ending_point':'Apply Scrum','additional_instructions':'Prefer short campus examples.'})
    assert result.status_code==200,result.text
    assert captured['short_assessment'] is True
    assert captured['additional_instructions']=='Prefer short campus examples.'
    assert 'Prefer short campus examples.' not in captured['approved_material']
    assert 'additional_instructions' not in result.json()

def test_complete_boundaries_remain_authoritative_without_a_focus(client,monkeypatch):
    from app import main
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','boundaries-test')
    monkeypatch.setattr(main,'infer_document_context',lambda *a:{'topic':'Requirements','course_level':'Undergraduate','prerequisite_knowledge':'An inferred prerequisite','objective_descriptions':['An inferred goal']})
    monkeypatch.setattr(main,'discover_resources',lambda *a:[])
    monkeypatch.setattr(main,'verify_resources',lambda *a:[])
    captured={}
    def generate(*a,**kwargs):
        captured.update(kwargs)
        return lesson()
    monkeypatch.setattr(main,'generate_learning_plan',generate)
    result=client.post('/internal/platform/lessons/prepare',headers={'X-Platform-Service':'boundaries-test'},json={'filename':'Course','material':lesson()['approved_material'],'starting_point':'Confirmed prior knowledge','ending_point':'Confirmed end goal'})
    assert result.status_code==200,result.text
    assert captured['short_assessment'] is True
    assert captured['prerequisite_knowledge']=='Confirmed prior knowledge'
    assert captured['objective_descriptions']==['Confirmed end goal']
