from dataclasses import replace
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_study import h,activate
from test_study_assist import help_request
from app import cloud_ai


def test_public_help_is_authored_and_private_sections_require_auth(client,monkeypatch):
    monkeypatch.setattr(cloud_ai,'_generate',lambda *a: (_ for _ in ()).throw(AssertionError('no public cloud')))
    assert client.get('/api/assistant/topics?section=finance').status_code==401
    response=client.get('/api/assistant/topics?section=auth'); assert response.status_code==200
    topic=response.json()['topics'][0]['id']
    r=client.post('/api/assistant/explain',json={'section':'auth','topic_id':topic})
    assert r.status_code==200 and r.json()['source']=='authored' and r.json()['request_id'] is None


def test_all_sections_strict_payload_and_material_version(client,mailbox):
    from app.assistant_content import SECTIONS
    headers=h(client,mailbox,'section-test@example.com')
    for section in SECTIONS:
        r=client.get('/api/assistant/topics',params={'section':section});assert r.status_code==200
        data=r.json();topic=data['topics'][0]['id']
        body={'section':section,'topic_id':topic}
        response=client.post('/api/assistant/explain',json=body,headers=headers)
        assert response.status_code==200 and response.json()['text']
    body={'section':'finance','topic_id':'finance-1','answer_text':'SECRET'}
    assert client.post('/api/assistant/explain',json=body,headers=headers).status_code==422
    assert client.post('/api/assistant/explain',json={'section':'finance','topic_id':'finance-1'}).status_code==403
    ref=client.get('/api/assistant/topics?section=nutrition').json()['materials'][0]
    body={'section':'nutrition','topic_id':'nutrition-1','material':{k:ref[k]for k in ('kind','id','version')}}
    assert client.post('/api/assistant/explain',json=body,headers=headers).status_code==200
    body['material']['version']='stale'
    assert client.post('/api/assistant/explain',json=body,headers=headers).status_code==409
    body['section']='finance';body['topic_id']='finance-1'
    assert client.post('/api/assistant/explain',json=body,headers=headers).status_code==404


def test_cloud_sections_payload_and_shared_budget(client,mailbox,monkeypatch):
    headers=h(client,mailbox,'shared-budget@example.com')
    plan=activate(client,headers,course='java',level='beginner',key='cloud-budget')
    client.app.state.settings=replace(client.app.state.settings,cloud_ai_enabled=True,cloud_ai_sections='finance',gemini_api_key='test')
    calls=[]
    cloud_ai.reset_runtime()
    monkeypatch.setattr(cloud_ai,'_generate',lambda *args: calls.append(args[2]) or {'text':'Сохраняйте операции по категориям.'})
    body={'section':'finance','topic_id':'finance-1'}
    result=client.post('/api/assistant/explain',json=body,headers=headers).json()
    assert result['source']=='cloud_ai'
    assert 'shared-budget' not in str(calls) and 'user_id' not in str(calls)
    for _ in range(19):client.post('/api/assistant/explain',json=body,headers=headers)
    r=client.post('/api/study/assist',json=help_request(plan),headers=headers)
    assert r.status_code==200 and r.json()['source']=='authored'
    assert len(calls)==1


def test_owned_feedback_cleanup_and_report(client,mailbox):
    from app.models import AssistantRequest,User
    from app.cleanup import cleanup_assistant
    from app.db import utc_now
    headers=h(client,mailbox,'feedback-sections@example.com')
    r=client.post('/api/assistant/explain',json={'section':'personal','topic_id':'personal-1'},headers=headers).json()
    payload={'request_id':r['request_id'],'helped':True}
    assert client.post('/api/assistant/feedback',json=payload,headers=headers).status_code==200
    assert client.post('/api/assistant/feedback',json=payload,headers=headers).status_code==409
    other=h(client,mailbox,'feedback-other@example.com')
    assert client.post('/api/assistant/feedback',json=payload,headers=other).status_code==404
    assert client.get('/api/assistant/report').status_code==200
    client.app.state.settings=replace(client.app.state.settings,environment='production')
    assert client.get('/api/assistant/report').status_code==404
    with Session(client.app.state.engine) as db:
        row=db.get(AssistantRequest,payload['request_id']);row.created_at=utc_now()-timedelta(days=31);db.commit()
        owner_id=row.user_id
        assert cleanup_assistant(db)==1;db.commit()
        assert db.get(User,owner_id)
        assert 'text' not in AssistantRequest.__table__.columns
