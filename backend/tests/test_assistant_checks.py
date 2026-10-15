from test_study import h


def test_owned_check_replay_and_separate_progress(client,mailbox):
    headers=h(client,mailbox,'companion@example.com')
    ref=client.get('/api/assistant/topics?section=java').json()['materials'][0]
    body={'section':'java','material':{k:ref[k]for k in ('kind','id','version')}}
    issued=client.post('/api/assistant/checks/issue',json=body,headers=headers)
    assert issued.status_code==200
    data=issued.json()
    assert data['available'] and 'correct_option_id' not in data['question']
    answer={'token':data['token'],'option_id':data['question']['options'][0]['id']}
    first=client.post('/api/assistant/checks/answer',json=answer,headers=headers)
    assert first.status_code==200
    assert client.post('/api/assistant/checks/answer',json=answer,headers=headers).json()==first.json()
    answer['option_id']=data['question']['options'][1]['id']
    assert client.post('/api/assistant/checks/answer',json=answer,headers=headers).status_code==409


def test_tamper_unknown_option_and_stale_content(client,mailbox,monkeypatch):
    from app import assistant_learning
    from dataclasses import replace
    headers=h(client,mailbox,'companion-stale@example.com')
    ref=client.get('/api/assistant/topics?section=java').json()['materials'][0]
    body={'section':'java','material':{k:ref[k]for k in ('kind','id','version')}}
    data=client.post('/api/assistant/checks/issue',json=body,headers=headers).json()
    assert client.post('/api/assistant/checks/answer',json={'token':data['token']+'x','option_id':'0'},headers=headers).status_code==409
    assert client.post('/api/assistant/checks/answer',json={'token':data['token'],'option_id':'unknown'},headers=headers).status_code==422
    bank=assistant_learning.all_checks()
    monkeypatch.setattr(assistant_learning,'all_checks',lambda:tuple(replace(c,explanation='edited')for c in bank))
    assert client.post('/api/assistant/checks/answer',json={'token':data['token'],'option_id':'0'},headers=headers).status_code==409


def test_source_content_edit_invalidates_issued_question(client,mailbox,monkeypatch):
    from app import assistant_learning
    from dataclasses import replace
    headers=h(client,mailbox,'source-edit@example.com')
    ref=client.get('/api/assistant/topics?section=java').json()['materials'][0]
    body={'section':'java','material':{k:ref[k]for k in ('kind','id','version')}}
    data=client.post('/api/assistant/checks/issue',json=body,headers=headers).json()
    original=assistant_learning.resolve_material
    monkeypatch.setattr(assistant_learning,'resolve_material',lambda *a,**kw:replace(original(*a,**kw),text='Updated source content'))
    assert client.post('/api/assistant/checks/answer',json={'token':data['token'],'option_id':'0'},headers=headers).status_code==409


def test_check_never_completes_lesson_and_rejects_archived_context(client,mailbox):
    from test_study import activate
    from sqlalchemy import select,func
    from sqlalchemy.orm import Session
    from app.models import StudyPlan,StudyAttempt,AssistantCheckAttempt
    headers=h(client,mailbox,'context-check@example.com')
    plan=activate(client,headers,course='java',level='beginner',key='context-check')
    with Session(client.app.state.engine)as db:
        actual=db.get(StudyPlan,plan['id'])
        ref={'kind':'lesson','id':actual.course_id+':'+actual.lesson_ids[0],'version':actual.version}
    body={'section':'java','material':ref,'study_context':{'plan_id':plan['id'],'lesson_id':ref['id'].split(':')[1]}}
    # Public section checks accept current-version material only.
    result=client.post('/api/assistant/checks/issue',json=body,headers=headers)
    if result.status_code==200 and result.json()['available']:
        data=result.json()
        with Session(client.app.state.engine)as db:
            actual=db.get(StudyPlan,plan['id']);actual.archived_at=__import__('app.db',fromlist=['utc_now']).utc_now();db.commit()
        assert client.post('/api/assistant/checks/answer',json={'token':data['token'],'option_id':data['question']['options'][0]['id']},headers=headers).status_code==409
    else:assert result.status_code==409
    with Session(client.app.state.engine)as db:
        assert db.scalar(select(func.count()).select_from(StudyAttempt))==0
        assert db.scalar(select(func.count()).select_from(AssistantCheckAttempt))==0
