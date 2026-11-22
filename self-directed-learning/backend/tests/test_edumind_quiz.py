"""EduMind's quiz is the primary source for SDL authoring, never a silent fallback."""
import copy
import json

import httpx
import pytest

from app import edumind_quiz, openai_client
from test_api import client, lesson


def generated_quiz():
    plan = lesson()
    questions = []
    for question in plan['diagnostic_quiz']:
        questions.append({
            'question': question['question'], 'scenario': '', 'options': question['options'],
            'correct_options': [question['correct_index']], 'difficulty_level': question['difficulty'],
            'tags': ['Requirements'], 'source': 'Uploaded course material',
            'source_id': 'S1', 'objective_id': 'OBJ1',
            **{key: question[key] for key in ('concept', 'explanation', 'hint')},
            'wrong_option_feedback': [{'option_index': index, 'explanation': text} for index, text in enumerate(question['distractor_misconceptions']) if index != question['correct_index']],
            'worked_example': 'For a library service, classify search behavior separately from its response-time constraint.',
            'reasoning_rubric': plan['objectives'][0]['rubric'],
        })
    for question in questions:
        question['scenario'] = 'A library team must reconcile a fast search requirement with a strict operating budget.'
    return {'message': 'Five questions prepared.', 'questions': questions}


def test_edumind_maps_every_support_field_to_existing_sdl_format():
    source = generated_quiz()
    questions = edumind_quiz.adapt_questions(source, {'OBJ1': 'Requirements'}, lesson()['approved_material'])
    assert len(questions) == 5
    for index, question in enumerate(questions):
        assert question['id'] == f'Q{index + 1}'
        assert question['correct_index'] == source['questions'][index]['correct_options'][0]
        assert edumind_quiz.source_passages(lesson()['approved_material'])['S1'] in question['material_reference']
        for field in ('hint', 'worked_example', 'explanation', 'reasoning_rubric'):
            assert question[field] == source['questions'][index][field]


@pytest.mark.parametrize('case', ['count', 'multiple_answers', 'boolean_key', 'bad_index',
                                  'duplicate_options', 'blank_option', 'unknown_objective',
                                  'fake_quote', 'missing_feedback', 'wrong_feedback_index', 'echo_feedback', 'missing_scenario', 'repeat', 'levels', 'hint_leak'])
def test_invalid_generation_is_rejected(case):
    output = generated_quiz()
    question = output['questions'][0]
    if case == 'count': output['questions'].pop()
    if case == 'multiple_answers': question['correct_options'] = [0, 1]
    if case == 'boolean_key': question['correct_options'] = [True]
    if case == 'bad_index': question['correct_options'] = [4]
    if case == 'duplicate_options': question['options'][1] = question['options'][0].upper()
    if case == 'blank_option': question['options'][1] = '  '
    if case == 'unknown_objective': question['objective_id'] = 'OTHER'
    if case == 'fake_quote': question['source_id'] = 'UNKNOWN'
    if case == 'missing_feedback': question['wrong_option_feedback'] = []
    if case == 'wrong_feedback_index': question['wrong_option_feedback'][0]['option_index'] = question['correct_options'][0]
    if case == 'echo_feedback': question['wrong_option_feedback'][0]['explanation'] = question['options'][question['wrong_option_feedback'][0]['option_index']]
    if case == 'missing_scenario': output['questions'][2]['scenario'] = ''
    if case == 'repeat': output['questions'][1]['question'] = question['question']
    if case == 'levels': output['questions'].reverse()
    if case == 'hint_leak': question['hint'] = question['options'][question['correct_options'][0]]
    with pytest.raises(ValueError):
        edumind_quiz.adapt_questions(output, {'OBJ1': 'Requirements'}, lesson()['approved_material'])


def test_feedback_is_attached_to_its_actual_option_index():
    output = generated_quiz()
    key = output['questions'][0]['correct_options'][0]
    output['questions'][0]['wrong_option_feedback'].reverse()
    result = edumind_quiz.adapt_questions(output, {'OBJ1': 'Requirements'}, lesson()['approved_material'])
    assert result[0]['correct_index'] == key
    assert result[0]['distractor_misconceptions'][key] == ''
    for item in output['questions'][0]['wrong_option_feedback']:
        assert result[0]['distractor_misconceptions'][item['option_index']] == item['explanation']


def test_primary_edumind_quiz_is_passed_to_lesson_authoring_and_cannot_be_overwritten(client, monkeypatch):
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    requests = []
    source = generated_quiz()
    plan = lesson()
    def provider(self, url, **kwargs):
        payload = kwargs['json']
        name = payload['response_format']['json_schema']['name']
        requests.append(name)
        assert payload['response_format']['json_schema']['strict'] is True
        if name == 'edumind_quiz':
            assert 'expert professor' in json.loads(payload['messages'][1]['content'])['edumind_template']
            result = source
        else:
            inputs = json.loads(payload['messages'][1]['content'])
            assert inputs['approved_quiz_draft'][0]['question'].endswith(source['questions'][0]['question'])
            assert 'diagnostic_quiz' not in payload['response_format']['json_schema']['schema']['properties']
            result = copy.deepcopy(plan)
            result['objectives'][0]['id'] = 'OBJ1'
            result['learning_assets'][0]['objective_id'] = 'OBJ1'
            result['diagnostic_quiz'][0]['question'] = 'A replacement quiz must never be accepted.'
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result)}}]})
    monkeypatch.setattr(httpx.Client, 'post', provider)
    result = openai_client.generate_learning_plan(plan['topic'], 'Undergraduate',
        approved_material=plan['approved_material'], objective_descriptions=[plan['objectives'][0]['description']])
    assert requests == ['edumind_quiz', 'lesson_draft']
    assert result['diagnostic_quiz'][0]['question'].endswith(source['questions'][0]['question'])
    assert result['content_approved'] is False


@pytest.mark.parametrize('failure', ['timeout', 'invalid', 'refusal', 'truncated', 'authentication'])
def test_edumind_failure_stops_before_lesson_generation(client, monkeypatch, failure):
    monkeypatch.setattr(openai_client, 'runtime_ai_mode', lambda: 'openai')
    calls = []
    def provider(self, url, **kwargs):
        calls.append(kwargs['json']['response_format']['json_schema']['name'])
        if failure == 'timeout': raise httpx.ReadTimeout('timeout')
        if failure == 'authentication': return httpx.Response(401, request=httpx.Request('POST', url))
        result = generated_quiz()
        if failure == 'invalid': result['questions'].pop()
        return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{
            'finish_reason': 'length' if failure == 'truncated' else 'stop',
            'message': {'content': json.dumps(result), 'refusal': 'Refused' if failure == 'refusal' else None},
        }]})
    monkeypatch.setattr(httpx.Client, 'post', provider)
    with pytest.raises(ValueError, match='EduMind.*retry'):
        openai_client.generate_learning_plan('Requirements', 'Undergraduate',
            approved_material=lesson()['approved_material'], objective_descriptions=['Apply requirements'])
    assert calls == ['edumind_quiz']


def test_short_edumind_contract_keeps_three_levels_and_source_checks():
    output = generated_quiz()
    output['questions'] = output['questions'][:3]
    levels = ['foundational', 'understanding', 'application']
    questions = edumind_quiz.adapt_questions(output, {'OBJ1':'Requirements'}, lesson()['approved_material'], levels)
    assert [q['difficulty'] for q in questions] == levels
    output['questions'][1]['source_id'] = 'invented'
    with pytest.raises(ValueError, match='passage'):
        edumind_quiz.adapt_questions(output, {'OBJ1':'Requirements'}, lesson()['approved_material'], levels)

def test_long_source_passages_fit_the_student_quiz_contract():
    material=('Developers inspect progress toward the Sprint Goal and adapt the Sprint Backlog while maintaining product quality.\n\n'*35)
    quiz=edumind_quiz.adapt_questions(generated_quiz(),{'OBJ1':'Requirements'},material)
    assert len(quiz)==5
    assert all(len(q['material_reference'])<=1000 for q in quiz)
    assert all(edumind_quiz.source_passages(material)[q['material_reference'].split(': ',1)[0]] in q['material_reference'] for q in quiz)

def test_quiz_schema_errors_report_the_field_without_echoing_source_content(client,monkeypatch):
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'openai')
    private='PRIVATE GENERATED TEXT '
    output=generated_quiz();output['questions'][0]['hint']=private*60
    def provider(self,url,**kwargs):
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    with pytest.raises(ValueError) as caught:
        edumind_quiz.generate_quiz('Requirements','Undergraduate',lesson()['approved_material'],{'OBJ1':'Requirements'},'Undergraduate','Programming')
    assert 'questions.0.hint' in str(caught.value)
    assert '1000' in str(caught.value)
    assert private not in str(caught.value)

SHORT_LEVELS=['foundational','understanding','application']
SHORT_OBJECTIVES={'OBJ1':'Distinguish behavior from quality requirements.','OBJ2':'Evaluate measurable quality constraints.','OBJ3':'Apply consistency checks to conflicting requirements.'}

def keyed_quiz():
    raw=generated_quiz()
    questions={}
    for index,objective_id in enumerate(SHORT_OBJECTIVES):
        question=copy.deepcopy(raw['questions'][index])
        question.pop('objective_id')
        questions[objective_id]=question
    return {'message':'Quiz prepared.','questions':questions}


def test_same_call_plans_from_original_inputs_and_requires_all_three_slots(monkeypatch):
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'openai')
    inputs={'learning_focus':'Analyze system requirements for a campus service.','concepts_and_subquestions':['Behavior','Quality','Measurability','Conflicts','Tradeoffs'],'prior_knowledge':'Basic programming, no requirements experience.','intended_learning_outcomes':'Classify, measure, and resolve requirements using evidence.'}
    calls=[]
    def provider(self,url,**kwargs):
        payload=kwargs['json'];calls.append(payload)
        context=json.loads(payload['messages'][1]['content'])
        assert context['instructor_inputs']==inputs
        assert context['source_passages']==edumind_quiz.source_passages(lesson()['approved_material'])
        assert context['instructor_teaching_preferences']=='Use a university project.'
        template=context['edumind_template']
        for phrase in ('within THIS generation call','not the first concepts listed','at least TWO','exactly one','parallel options','EACH of the three distractors','without naming','source_id'):
            assert phrase in template
        assert 'Do not output' in template
        schema=payload['response_format']['json_schema']['schema']
        slots=schema['properties']['questions']
        assert set(slots['required'])==set(SHORT_OBJECTIVES)
        assert slots['additionalProperties'] is False
        for index,objective_id in enumerate(SHORT_OBJECTIVES):
            assert slots['properties'][objective_id] == {'$ref':'#/$defs/EduMindQuestion'}
            fields=schema['$defs']['EduMindQuestion']['properties']
            assert 'objective_id' not in fields
            assert fields['difficulty_level']['enum']==SHORT_LEVELS
            assert context['objective_slots'][objective_id]==SHORT_LEVELS[index]
            assert fields['question']['maxLength']+fields['scenario']['maxLength']+2<=2000
            assert fields['options']['minItems']==fields['options']['maxItems']==4
            assert fields['correct_options']['minItems']==fields['correct_options']['maxItems']==1
        result=keyed_quiz()
        # Object serialization order is irrelevant; the server uses configured slots.
        result['questions']=dict(reversed(list(result['questions'].items())))
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    result=edumind_quiz.generate_quiz('Requirements','Undergraduate',lesson()['approved_material'],SHORT_OBJECTIVES,'Undergraduate',inputs['prior_knowledge'],levels=SHORT_LEVELS,distinct_objectives=True,instructor_inputs=inputs,additional_instructions='Use a university project.')
    assert len(calls)==1
    assert [q['id'] for q in result]==['Q1','Q2','Q3']
    assert [q['objective_id'] for q in result]==list(SHORT_OBJECTIVES)
    assert [q['difficulty'] for q in result]==SHORT_LEVELS
    assert all(len(q['options'])==4 and isinstance(q['correct_index'],int) for q in result)
    assert all('instructor_inputs' not in q and 'planning' not in q for q in result)


@pytest.mark.parametrize('defect',['missing_slot','extra_slot','changed_objective','invented_source'])
def test_three_slot_response_cannot_omit_or_relabel_an_objective(defect):
    output=keyed_quiz()
    if defect=='missing_slot':output['questions'].pop('OBJ2')
    if defect=='extra_slot':output['questions']['OTHER']=output['questions']['OBJ1']
    if defect=='changed_objective':output['questions']['OBJ1']['objective_id']='OBJ2'
    if defect=='invented_source':output['questions']['OBJ1']['source_id']='invented'
    with pytest.raises(ValueError):edumind_quiz.adapt_questions(output,SHORT_OBJECTIVES,lesson()['approved_material'],SHORT_LEVELS)


def test_real_instructor_inputs_are_forwarded_through_lesson_generation(client,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'discover_resources',lambda *a:[])
    monkeypatch.setattr(main,'verify_resources',lambda *a:[])
    captured={}
    def generate(*args,**kwargs):captured.update(kwargs);return lesson()
    monkeypatch.setattr(main,'generate_learning_plan',generate)
    raw_focus='A complete instructor focus.\nInstructor sub-questions to address:\nFirst concept\nSecond concept\nFifth important concept'
    main._document_plan(lesson()['approved_material'],'course.pdf',starting_point='Basic programming',ending_point='Evaluate and justify decisions',learning_focus=raw_focus,allow_course_material_fallback=True)
    assert captured['instructor_inputs']=={'learning_focus':'A complete instructor focus.','concepts_and_subquestions':['First concept','Second concept','Fifth important concept'],'prior_knowledge':'Basic programming','intended_learning_outcomes':'Evaluate and justify decisions'}


def test_budget_selection_keeps_every_objective_and_original_citations():
    passages={'S1':'irrelevant appendix '*100, 'S2':'alpha mechanisms '*30,
              'S3':'beta relationships '*30, 'S4':'gamma decisions '*30}
    selected=edumind_quiz._budget_passages(passages, {'A':'alpha','B':'beta','C':'gamma'}, 1800)
    assert set(selected)=={'S2','S3','S4'}
    assert all(selected[key]==passages[key] for key in selected)
    with pytest.raises(ValueError,match='every objective'):
        edumind_quiz._budget_passages(passages, {'A':'missing subject'},1800)
    with pytest.raises(ValueError,match='every quiz objective'):
        edumind_quiz._budget_passages(passages, {'A':'alpha','B':'beta','C':'gamma'},100)


def test_quiz_rejects_citation_not_sent_to_provider():
    with pytest.raises(ValueError,match='passage'):
        edumind_quiz.adapt_questions(generated_quiz(), {'OBJ1':'Requirements'},
                                    lesson()['approved_material'], allowed_source_ids={'S2'})


@pytest.mark.parametrize('schema_mode',[True,False])
def test_size_rejection_retries_smaller_with_all_objectives_and_validates(monkeypatch,schema_mode):
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'groq')
    monkeypatch.setattr(openai_client,'_chat_settings',lambda:('https://provider.test', 'openai/gpt-oss-120b' if schema_mode else 'other', {}))
    monkeypatch.setenv('SDL_QUIZ_REQUEST_BUDGET_BYTES','100000')
    material='\n\n'.join(f'Requirements evidence group {i}: behavior and quality constraints matter. '*8 for i in range(12))
    requests=[]
    def provider(self,url,**kwargs):
        payload=kwargs['json'];requests.append(payload)
        if len(requests)==1:
            return httpx.Response(413,request=httpx.Request('POST',url))
        context=json.loads(payload['messages'][1]['content'])
        assert context['objectives']=={'OBJ1':'Requirements'}
        result=generated_quiz()
        for q in result['questions']:q['source_id']=next(iter(context['source_passages']))
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    quiz=edumind_quiz.generate_quiz('Requirements','Undergraduate',material,{'OBJ1':'Requirements'},'Undergraduate','None')
    assert len(requests)==2
    assert edumind_quiz._request_bytes(requests[1])<edumind_quiz._request_bytes(requests[0])
    assert len(quiz)==5
    assert material.startswith('Requirements evidence group 0')


def test_budgeted_request_preserves_late_objective_evidence(monkeypatch):
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'openai')
    monkeypatch.setenv('SDL_QUIZ_REQUEST_BUDGET_BYTES','17000')
    objectives={'OBJ1':'alpha mechanisms','OBJ2':'beta relationships','OBJ3':'gamma decisions'}
    material='\n\n'.join(['Appendix irrelevant background. '*25]*35+['alpha mechanisms '*30,'beta relationships '*30,'gamma decisions '*30])
    calls=[]
    def provider(self,url,**kwargs):
        payload=kwargs['json'];calls.append(payload)
        context=json.loads(payload['messages'][1]['content'])
        source=' '.join(context['source_passages'].values())
        assert all(term in source for term in ['alpha','beta','gamma'])
        assert edumind_quiz._request_bytes(payload)<=17000
        result=keyed_quiz()
        for oid,q in result['questions'].items():
            term=objectives[oid].split()[0]
            q['source_id']=next(key for key,text in context['source_passages'].items() if term in text)
        return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    monkeypatch.setattr(httpx.Client,'post',provider)
    assert len(edumind_quiz.generate_quiz('Topic','Undergraduate',material,objectives,'Undergraduate','None',levels=SHORT_LEVELS,distinct_objectives=True))==3
    assert len(calls)==1


def test_schema_compaction_preserves_fields_named_title_and_description():
    schema=edumind_quiz._compact_schema({'title':'Display title','type':'object','properties':{
        'title':{'type':'string','title':'Title'}, 'description':{'type':'string','description':'Help'}},
        'required':['title','description']})
    assert schema['properties']=={'title':{'type':'string'},'description':{'type':'string'}}
    assert schema['required']==['title','description']


def test_persistent_413_is_bounded_and_does_not_expose_provider_body(monkeypatch):
    monkeypatch.setattr(openai_client,'runtime_ai_mode',lambda:'groq')
    monkeypatch.setenv('SDL_QUIZ_REQUEST_BUDGET_BYTES','100000')
    material='\n\n'.join(f'Requirements evidence {i} about behavior and quality. '*10 for i in range(10))
    calls=[]
    def provider(self,url,**kwargs):
        calls.append(kwargs['json'])
        return httpx.Response(413,request=httpx.Request('POST',url),text='PRIVATE SOURCE DATA')
    monkeypatch.setattr(httpx.Client,'post',provider)
    with pytest.raises(ValueError,match='request size after request compaction') as caught:
        edumind_quiz.generate_quiz('Requirements','Undergraduate',material,{'OBJ1':'Requirements'},'Undergraduate','None')
    assert len(calls)==2
    assert 'PRIVATE SOURCE DATA' not in str(caught.value)
