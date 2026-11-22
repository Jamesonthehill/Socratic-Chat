"""Local transport policy checks; no external requests or service credentials."""
import httpx
import pytest
from fastapi import HTTPException
from platform_app.main import app as platform_application
from platform_app import shared_rag

@pytest.mark.parametrize('path,method,long_request',[
    ('/internal/platform/lessons/prepare','POST',True),
    ('/internal/platform/lessons/suggest-boundaries','POST',False),
    ('/internal/platform/rag/search','POST',False),
    ('/internal/platform/lessons/prepare','GET',False),
])
def test_only_lesson_preparation_has_a_longer_read_budget(monkeypatch,path,method,long_request):
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','local-test-token')
    monkeypatch.setenv('SELF_DIRECTED_LEARNING_URL','https://preview.invalid')
    monkeypatch.setattr(shared_rag,'_wait_for_service',lambda *a:None)
    seen={}
    class Client:
        def __init__(self,**kwargs):seen.update(kwargs)
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def request(self,method,url,**kwargs):return httpx.Response(200,request=httpx.Request(method,url),json={'ready':True})
    monkeypatch.setattr(shared_rag.httpx,'Client',Client)
    assert shared_rag.pipeline(method,path,json={})=={'ready':True}
    if long_request:
        assert seen['timeout'].read==480
        assert seen['timeout'].connect==15
    else:assert seen['timeout']==180


def test_timed_out_generation_is_not_replayed(monkeypatch):
    monkeypatch.setenv('PLATFORM_SERVICE_TOKEN','local-test-token')
    monkeypatch.setattr(shared_rag,'_wait_for_service',lambda *a:None)
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def request(self,*a,**k):calls.append(a);raise httpx.ReadTimeout('synthetic timeout')
    monkeypatch.setattr(shared_rag.httpx,'Client',Client)
    with pytest.raises(HTTPException) as caught:shared_rag.pipeline('POST','/internal/platform/lessons/prepare',json={})
    assert caught.value.status_code==504
    assert 'lesson generation' in caught.value.detail
    assert 'No automatic retry' in caught.value.detail
    assert len(calls)==1
