from dataclasses import replace
import json
from datetime import date
from test_study import activate, h
from test_study_assist import help_request


def test_production_cloud_help_receives_only_catalog_data(client, mailbox, monkeypatch):
    from app import cloud_ai
    client.app.state.settings = replace(client.app.state.settings, cloud_ai_enabled=True, gemini_api_key='test-key')
    headers=h(client,mailbox,'private-user@example.com');plan=activate(client,headers,course='java',level='beginner',key='cloud')
    captured=[]
    def fake(model,key,payload):
        captured.append(payload)
        return {'text':'Сопоставьте подготовку исходного кода и запуск программы.'}
    monkeypatch.setattr(cloud_ai,'_generate',fake)
    cloud_ai.reset_runtime()
    response=client.post('/api/study/assist',json=help_request(plan,stage='explain')|{'answer_text':'SECRET_PRIVATE_ANSWER','include_answer':True},headers=headers)
    assert response.status_code==200
    assert response.json()['source']=='cloud_ai'
    outgoing=json.dumps(captured)
    assert 'SECRET_PRIVATE_ANSWER' not in outgoing and 'private-user' not in outgoing and plan['id'] not in outgoing
    assert response.json()['allow_local_answer'] is False
    # Generic cached explanation must be reusable without a second upstream request.
    again=client.post('/api/study/assist',json=help_request(plan,stage='explain'),headers=headers)
    assert again.json()['source']=='cloud_ai' and len(captured)==1


def test_cloud_invalid_output_failure_and_spoiler_use_authored_fallback(monkeypatch):
    from app import cloud_ai
    from app.study_help import get_help_fragment
    fragment=get_help_fragment('java','v1','java-01',0,today=date(2026,10,15))
    for outcome in ({'text':'Компилирует исходник'}, {'text':''}, {'text':'x'*1001}, {'text':'https://untrusted.example/'}, {'text':123}, ['wrong']):
        cloud_ai.reset_runtime()
        monkeypatch.setattr(cloud_ai,'_generate',lambda *args:outcome)
        result=cloud_ai.explain_catalog_fragment(fragment,stage='hint',api_key='key',model='gemini-3.5-flash-lite')
        assert result['source']=='authored'
    def fail(*args): raise TimeoutError('secret-provider-error')
    cloud_ai.reset_runtime();monkeypatch.setattr(cloud_ai,'_generate',fail)
    assert cloud_ai.explain_catalog_fragment(fragment,stage='explain',api_key='key',model='gemini-3.5-flash-lite')['source']=='authored'


def test_cloud_never_reviews_personal_attempts_or_runs_without_key(monkeypatch):
    from app import cloud_ai
    from app.study_help import get_help_fragment
    fragment=get_help_fragment('java','v1','java-01',0,today=date(2026,10,15))
    def forbidden(*args):raise AssertionError('Must not call external service')
    monkeypatch.setattr(cloud_ai,'_generate',forbidden)
    for stage,key in [('review','key'),('explain','')]:
        assert cloud_ai.explain_catalog_fragment(fragment,stage=stage,api_key=key,model='gemini-3.5-flash-lite')['source']=='authored'


def test_cloud_has_process_rate_and_busy_bounds(monkeypatch):
    from app import cloud_ai
    from app.study_help import get_help_fragment
    fragment=get_help_fragment('java','v1','java-01',0,today=date(2026,10,15))
    cloud_ai.reset_runtime()
    monkeypatch.setattr(cloud_ai,'_generate',lambda *args:{'text':'Подготовка исходного кода и запуск программы — разные этапы.'})
    cloud_ai._busy.acquire()
    try:assert cloud_ai.explain_catalog_fragment(fragment,stage='explain',api_key='key',model='m')['source']=='authored'
    finally:cloud_ai._busy.release()
    for i in range(3):
        assert cloud_ai.explain_catalog_fragment(fragment,stage='explain',api_key='key',model=f'm{i}')['source']=='cloud_ai'
    assert cloud_ai.explain_catalog_fragment(fragment,stage='explain',api_key='key',model='next')['source']=='authored'


def test_transport_keeps_key_in_header_and_bounds_output(monkeypatch):
    from app import cloud_ai
    sent=[]
    class Response:
        status=200
        def read(self,limit):
            assert limit==16385
            return json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"text":"Короткое объяснение."}'}]}}]}).encode()
    class Connection:
        def __init__(self,host,timeout):assert host=='generativelanguage.googleapis.com' and timeout==12
        def request(self,method,path,body,headers):sent.append((path,headers))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(cloud_ai.http.client,'HTTPSConnection',Connection)
    assert cloud_ai._generate('gemini-3.5-flash-lite','SECRET_KEY',{})['text']
    assert 'SECRET_KEY' not in sent[0][0]
    assert sent[0][1]['x-goog-api-key']=='SECRET_KEY'


def test_settings_do_not_expose_gemini_key(client):
    settings=replace(client.app.state.settings,gemini_api_key='SECRET_KEY')
    assert 'SECRET_KEY' not in repr(settings)


def test_malformed_successful_provider_json_always_falls_back(monkeypatch):
    from app import cloud_ai
    from app.study_help import get_help_fragment
    fragment=get_help_fragment('java','v1','java-01',0,today=date(2026,10,15))
    malformed=[{'candidates':[None]}, {'candidates':None}, [],
               {'candidates':[{'finishReason':'STOP','content':None}]},
               {'candidates':[{'finishReason':'STOP','content':{'parts':[None]}}]}]
    for data in malformed:
        class Response:
            status=200
            def read(self,limit):return json.dumps(data).encode()
        class Connection:
            def __init__(self,*args,**kwargs):pass
            def request(self,*args):pass
            def getresponse(self):return Response()
            def close(self):pass
        cloud_ai.reset_runtime()
        monkeypatch.setattr(cloud_ai.http.client,'HTTPSConnection',Connection)
        result=cloud_ai.explain_catalog_fragment(fragment,stage='explain',api_key='key',model='gemini-3.5-flash-lite')
        assert result['source']=='authored'
