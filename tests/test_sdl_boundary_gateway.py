from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from platform_app.main import app as platform_application
from platform_app import workspace, routes
from platform_app.schemas import SelfDirectedConfig

@pytest.fixture
def setup_gateway(monkeypatch):
    @contextmanager
    def connection(): yield Mock()
    monkeypatch.setattr(workspace.store,'connection',connection)
    item={'id':'a1','title':'Scrum','course_id':'c1','tool':'self-directed-learning','status':'draft','instructions':'Student description', 'config':{'document_ids':['d1'],'prompt':'Scrum','starting_point':'','ending_point':'Apply Scrum','custom_questions':['Daily Scrum'],'additional_instructions':'Use campus examples.'}}
    access=Mock(return_value=item)
    monkeypatch.setattr(workspace,'get_assignment',access)
    monkeypatch.setattr(workspace.shared_rag,'course_chunks',lambda *a:[{'text':'The team inspects progress and adapts the Sprint Backlog.'}])
    pipeline=Mock(return_value={'starting_point':'Basic teamwork','ending_point':'Apply Scrum'})
    monkeypatch.setattr(workspace.shared_rag,'pipeline',pipeline)
    return item,access,pipeline

def test_suggestion_checks_management_and_keeps_draft_unmodified(setup_gateway):
    item,access,pipeline=setup_gateway
    result=workspace.suggest_sdl_boundaries('a1',{'user_id':'teacher'})
    assert result['starting_point']=='Basic teamwork'
    assert item['config']['starting_point']==''
    access.assert_called_once_with(access.call_args.args[0],'a1',{'user_id':'teacher'},manage=True)
    assert pipeline.call_args.kwargs['json']['additional_instructions']=='Use campus examples.'
    assert pipeline.call_args.args[1]=='/internal/platform/lessons/suggest-boundaries'

def test_missing_boundary_blocks_generation(setup_gateway):
    _,_,pipeline=setup_gateway
    with pytest.raises(HTTPException) as caught: workspace.prepare_sdl('a1',{'user_id':'teacher'})
    assert caught.value.status_code==422
    pipeline.assert_not_called()

def test_private_notes_round_trip_only_to_instructors():
    config=SelfDirectedConfig(additional_instructions='Use campus examples.').model_dump()
    item={'tool':'self-directed-learning','status':'draft','config':config,'snapshot':None}
    assert routes.public_assignment(item,manage=True)['config']['additional_instructions']=='Use campus examples.'
    student=routes.public_assignment(item,manage=False)
    assert 'config' not in student
    assert 'additional_instructions' not in str(student)

def test_confirmed_inputs_forward_preferences_without_changing_source(setup_gateway):
    item,_,pipeline=setup_gateway
    item['config']['starting_point']='Confirmed prior knowledge'
    pipeline.return_value={'title':'Draft lesson'}
    result=workspace.prepare_sdl('a1',{'user_id':'teacher'})
    request=pipeline.call_args.kwargs['json']
    assert request['starting_point']=='Confirmed prior knowledge'
    assert request['ending_point']=='Apply Scrum'
    assert request['additional_instructions']=='Use campus examples.'
    assert 'Use campus examples.' not in request['material']
    assert result['learning_plan']=={'title':'Draft lesson'}


def test_sdl_prerequisites_save_without_attachment_lookup(monkeypatch):
    from types import SimpleNamespace
    lookup=Mock(side_effect=AssertionError('SDL draft save must not require indexed attachments'))
    monkeypatch.setattr(routes.db,'list_rag_files',lookup)
    routes.validate_activity_documents(SimpleNamespace(tool='self-directed-learning',course_id='c1',
        config={'starting_point':'Basic teamwork','document_ids':['stale-document']}))
    lookup.assert_not_called()


def test_other_tools_still_reject_cross_course_documents(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(routes.db,'list_rag_files',lambda **kwargs:[{'document_id':'course-document'}])
    with pytest.raises(HTTPException) as caught:
        routes.validate_activity_documents(SimpleNamespace(tool='socratic',course_id='c1',
            config={'document_ids':['other-course-document']}))
    assert caught.value.status_code==422


def test_sdl_source_read_still_rejects_cross_course_documents(monkeypatch):
    from platform_app import shared_rag
    monkeypatch.setattr(shared_rag.db,'list_rag_files',lambda **kwargs:[{'document_id':'course-document'}])
    with pytest.raises(HTTPException):
        shared_rag.course_chunks('c1',['other-course-document'])
