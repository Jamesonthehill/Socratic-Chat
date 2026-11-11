"""Step surveys use isolated database fixtures and mocked model calls only."""
import json
from types import SimpleNamespace
from uuid import uuid4

from platform_tests.test_assignments import draft, publish
import pytest
from platform_app import step_surveys, store


@pytest.fixture(autouse=True)
def isolate_new_survey_assignments(database):
    with store.connection() as conn:
        before = {row["id"] for row in conn.execute("SELECT id FROM assignments_platform").fetchall()}
    yield
    with store.connection() as conn:
        created = [row["id"] for row in conn.execute("SELECT id FROM assignments_platform").fetchall() if row["id"] not in before]
        if created:
            conn.execute("DELETE FROM assignment_attempts_platform WHERE assignment_id=ANY(%s)", (created,))
            conn.execute("DELETE FROM assignments_platform WHERE id=ANY(%s)", (created,))


def activity(client, roster, monkeypatch):
    item, _ = draft(client, roster, config={"learning_steps": [
        {"title": "Inspect evidence", "goal": "Explain why evidence should guide the next decision.", "evidence_quote": "Review feedback before changing a plan.", "source_chunk_id": "source-1", "scenario": "The team receives new feedback.", "question": "What would you inspect?"},
        {"title": "Adapt a plan", "goal": "Apply new evidence to revise a concrete plan.", "evidence_quote": "Apply feedback to revise a plan.", "source_chunk_id": "source-1", "scenario": "The first change is reviewed.", "question": "What would you adjust?"},
    ]})
    publish(client, roster, item, monkeypatch)
    return f"/api/platform/assignments/{item['id']}", roster['headers']


def survey_payload():
    return {"title": "Reflect on the evidence", "questions": [
        {"id": str(uuid4()), "kind": "confidence", "prompt": "How confident are you about inspecting evidence?"},
        {"id": str(uuid4()), "kind": "text", "prompt": "Which part of inspecting evidence was confusing?"},
        {"id": str(uuid4()), "kind": "text", "prompt": "Explain how evidence informs your next decision."},
    ], "publish": True}


def test_survey_round_trip_is_ungraded_versioned_and_authorized(client, roster, monkeypatch):
    url, h = activity(client, roster, monkeypatch)
    payload = survey_payload()
    published = client.put(url+'/step-surveys/0', headers=h['prof'], json=payload)
    assert published.status_code == 200, published.text
    survey = published.json()['published']
    assert client.get(url+'/step-surveys', headers=h['other_prof']).status_code == 403
    assert client.get(url+'/step-surveys', headers=h['other_student']).status_code == 404
    assert client.get(url+'/step-surveys', headers=h['student']).json()['steps'] == []
    before = client.post(url+'/start', headers=h['student']).json()
    visible = client.get(url+'/step-surveys', headers=h['student']).json()['steps']
    assert len(visible) == 1 and visible[0]['published']['version'] == survey['version']
    assert 'draft' not in visible[0]
    answers = {q['id']: 3 if q['kind']=='confidence' else 'I would inspect feedback before changing the plan.' for q in survey['questions']}
    submit = {'version':survey['version'],'answers':answers}
    assert client.post(url+'/step-surveys/0/submit', headers=h['student'], json=submit).status_code == 200
    assert client.post(url+'/step-surveys/0/submit', headers=h['student'], json=submit).status_code == 200
    after = client.get(url+'/attempt', headers=h['student']).json()
    assert after['engine_state']['socratic'] == before['engine_state']['socratic']
    assert after['status'] == before['status']
    assert after['messages'] == before['messages']
    assert client.get(url+'/step-surveys', headers=h['student']).json()['steps'][0]['submitted']
    groups = client.get(url+'/step-survey-analysis', headers=h['prof']).json()['groups']
    assert len(groups)==1 and len(groups[0]['responses'])==1
    assert groups[0]['responses'][0]['answers'] == answers
    assert client.get(url+'/step-survey-analysis', headers=h['student']).status_code == 403
    assert client.get(url+'/step-survey-analysis', headers=h['other_prof']).status_code == 403
    # Saving a draft leaves the student-facing publication intact.
    edited = {**payload,'publish':False,'title':'Revised instructor draft'}
    client.put(url+'/step-surveys/0', headers=h['prof'], json=edited)
    assert client.get(url+'/step-surveys', headers=h['student']).json()['steps'][0]['published']['title']==survey['title']
    # Re-publishing retains earlier answers with their original question snapshot.
    edited['publish']=True
    new = client.put(url+'/step-surveys/0', headers=h['prof'], json=edited).json()['published']
    assert new['version'] != survey['version']
    assert client.post(url+'/step-surveys/0/submit', headers=h['student'], json=submit).status_code == 409
    groups = client.get(url+'/step-survey-analysis', headers=h['prof']).json()['groups']
    assert groups[0]['survey']['title'] == survey['title']
    assert client.get(url+'/reflection-analysis', headers=h['prof']).status_code == 200


def test_surveys_reject_future_steps_invalid_answers_and_unreviewed_access(client, roster, monkeypatch):
    url, h = activity(client, roster, monkeypatch)
    payload = survey_payload()
    assert client.put(url+'/step-surveys/0',headers=h['student'],json=payload).status_code==403
    assert client.post(url+'/step-surveys/0/generate',headers=h['other_prof'],json={}).status_code==403
    for index in [0,1]:
        response = client.put(url+f'/step-surveys/{index}',headers=h['prof'],json=payload)
        assert response.status_code==200
        if index==0: survey=response.json()['published']
        else: future=response.json()['published']
    client.post(url+'/start',headers=h['student'])
    assert [s['index'] for s in client.get(url+'/step-surveys',headers=h['student']).json()['steps']]==[0]
    answers={q['id']:3 if q['kind']=='confidence' else 'A meaningful reflection.' for q in payload['questions']}
    assert client.post(url+'/step-surveys/1/submit',headers=h['student'],json={'version':future['version'],'answers':answers}).status_code==403
    for bad in [{}, {**answers,payload['questions'][0]['id']:9}, {**answers,payload['questions'][0]['id']:True}, {**answers,payload['questions'][1]['id']:' '}]:
        assert client.post(url+'/step-surveys/0/submit',headers=h['student'],json={'version':survey['version'],'answers':bad}).status_code==422


def test_generation_uses_selected_step_and_never_publishes_it_automatically(client, roster, monkeypatch):
    url,h=activity(client,roster,monkeypatch)
    calls=[]
    async def complete(_key,_url,request):
        calls.append(request)
        content={'title':'Reflect on adapting a plan','questions':[
            {'kind':'confidence','prompt':'How confident are you about adapting a plan?'},
            {'kind':'text','prompt':'What about adapting a plan was confusing?'},
            {'kind':'text','prompt':'Explain how evidence would change your plan.'},
        ]}
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))])
    monkeypatch.setattr(step_surveys.settings,'llm_client_config',lambda _role:('OpenAI','test-key','test-url','test-model'))
    monkeypatch.setattr(step_surveys,'chat_completion',complete)
    response=client.post(url+'/step-surveys/1/generate',headers=h['prof'],json={})
    assert response.status_code==200,response.text
    assert len(response.json()['questions'])==3
    assert 'Adapt a plan' in calls[0]['messages'][1]['content']
    assert client.get(url+'/step-surveys',headers=h['prof']).json()['steps'][1].get('published') is None


def test_reflection_subtopics_can_collect_surveys_too(client,roster,monkeypatch):
    from platform_app import engines
    item,_=draft(client,roster,tool='reflections',config={'sub_topics':['Explain how evidence changed your decision.']})
    publish(client,roster,item,monkeypatch)
    url=f"/api/platform/assignments/{item['id']}";h=roster['headers']
    listed=client.get(url+'/step-surveys',headers=h['prof']).json()['steps']
    assert listed[0]['title']=='Explain how evidence changed your decision.'
    payload=survey_payload()
    response=client.put(url+'/step-surveys/0',headers=h['prof'],json=payload)
    assert response.status_code==200,response.text
    monkeypatch.setattr(engines,'start',lambda *_:{'messages':[{'role':'assistant','content':'Tell me what you learned.'}]})
    client.post(url+'/start',headers=h['student'])
    survey=client.get(url+'/step-surveys',headers=h['student']).json()['steps'][0]['published']
    answers={q['id']:4 if q['kind']=='confidence' else 'Evidence helped me revise the plan.' for q in survey['questions']}
    assert client.post(url+'/step-surveys/0/submit',headers=h['student'],json={'version':survey['version'],'answers':answers}).status_code==200
    assert len(client.get(url+'/step-survey-analysis',headers=h['prof']).json()['groups'])==1
