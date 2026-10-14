import json
from pathlib import Path
from datetime import timedelta
from app.tasks import local_date
from test_spheres import sign_in

COURSES=json.loads((Path(__file__).parents[1]/'app/content/study-v1.json').read_text())
def h(client,mailbox,email='one@example.com'):
    return {'X-CSRF-Token':sign_in(client,mailbox,email)}
def values(course='english',key='plan-1',previous=None,level='A2'):
    return dict(course_id=course,version='v1',level=level,goal='general',minutes=30,weekdays=[0,2,4],start_date=local_date('Asia/Almaty').isoformat(),expected_plan_id=previous,create_key=key)
def activate(client,headers,**kwargs):
    r=client.post('/api/study/plans',json=values(**kwargs),headers=headers)
    assert r.status_code==201,r.text
    return r.json()
def attempt(plan,lesson=None,key='attempt-1'):
    course=next(c for c in COURSES if c['id']==plan['course_id'])
    l=next(l for l in course['lessons'] if l['id']==(lesson or plan['lesson_ids'][0]))
    return dict(plan_id=plan['id'],lesson_id=l['id'],date=local_date('Asia/Almaty').isoformat(),answers=[q['answers'][0] for q in l['quiz']],evidence='Мой самостоятельный ответ и описание проверки результата.',self_checks=[True]*len(l['rubric']),portfolio_url='',create_key=key)


def test_catalog_audio_and_plan_preview_do_not_activate(client,mailbox):
    assert client.get('/api/study/catalog').status_code==401
    headers=h(client,mailbox)
    catalog=client.get('/api/study/catalog')
    assert catalog.status_code==200
    assert len(catalog.json()['items'])==4
    go=next(item for item in catalog.json()['items'] if item['id']=='go')
    assert go['version']=='v2' and go['lesson_count']==32
    backend=next(item for item in catalog.json()['items'] if item['id']=='java-backend')
    assert backend['version']=='v3' and backend['lesson_count']==14
    assert len(client.get('/api/study/courses/java-backend?version=v1').json()['lessons'])==8
    assert len(client.get('/api/study/courses/java-backend').json()['lessons'])==14
    assert client.post('/api/study/preview',json=values(course='java-backend',level='foundation')|{'version':'v2'},headers=headers).json()['lesson_count']==12
    preview=client.post('/api/study/preview',json=values(level='B1'),headers=headers)
    assert preview.status_code==200 and len(preview.json()['lesson_ids'])==16
    assert client.get('/api/study/state/english').json()['active_plan'] is None
    course=client.get('/api/study/courses/english').json()
    assert course['lessons'][0]['audio'].endswith('.wav')
    assert 'answers' not in course['lessons'][0]['quiz'][0]
    assert client.post('/api/study/plans',json=values()).status_code==403
    for change in [dict(level='C2'),dict(weekdays=[]),dict(minutes=5),dict(course_id='python'),dict(version='v99')]:
        assert client.post('/api/study/preview',json={**values(),**change},headers=headers).status_code in (404,422)


def test_weak_topics_use_latest_attempt_and_disappear_after_success(client, mailbox):
    headers=h(client,mailbox,'weak-topics@example.com')
    plan=activate(client,headers)
    wrong=attempt(plan,key='wrong')
    wrong['answers'][0]='Совершенно неверный ответ'
    response=client.post('/api/study/attempts',json=wrong,headers=headers)
    assert response.status_code==201 and not response.json()['passed']
    topics=client.get('/api/study/weak-topics/english').json()['items']
    assert topics and topics[0]['lesson_id']==wrong['lesson_id']
    assert topics[0]['prompt'] and topics[0]['explanation']
    correct=attempt(plan,key='correct')
    assert client.post('/api/study/attempts',json=correct,headers=headers).status_code==201
    assert client.get('/api/study/weak-topics/english').json()['items']==[]


def test_go_course_can_start_submit_and_resume(client, mailbox):
    headers = h(client, mailbox, 'go-study@example.com')
    go = json.loads((Path(__file__).parents[1] / 'app/content/study-go-v1.json').read_text())
    shown = client.get('/api/study/courses/go')
    assert shown.status_code == 200 and len(shown.json()['lessons']) == 32
    assert 'answers' not in shown.json()['lessons'][0]['quiz'][0]
    preview = client.post('/api/study/preview', json=values(course='go', level='beginner'), headers=headers)
    assert preview.status_code == 200 and preview.json()['lesson_count'] == 30
    plan = activate(client, headers, course='go', level='beginner', key='go-plan')
    first = go['lessons'][0]
    payload = dict(plan_id=plan['id'], lesson_id=first['id'], date=local_date('Asia/Almaty').isoformat(),
                   answers=[question['answers'][0] for question in first['quiz']],
                   evidence='Создал модуль и локально проверил вывод первой программы на Go.',
                   self_checks=[True] * len(first['rubric']), portfolio_url='', create_key='go-attempt')
    saved = client.post('/api/study/attempts', json=payload, headers=headers)
    assert saved.status_code == 201, saved.text
    assert saved.json()['passed']
    state = client.get('/api/study/state/go').json()
    assert state['completed'] == [first['id']]
    assert state['next_lesson_id'] == go['lessons'][1]['id']


def test_plan_idempotency_replacement_and_old_history(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    assert activate(client,headers)['id']==plan['id']
    payload=attempt(plan)
    saved=client.post('/api/study/attempts',json=payload,headers=headers)
    assert saved.status_code==201 and saved.json()['passed']
    assert client.post('/api/study/attempts',json=payload,headers=headers).json()['id']==saved.json()['id']
    assert client.post('/api/study/attempts',json={**payload,'evidence':'Совсем другой текст результата'},headers=headers).status_code==409
    state=client.get('/api/study/state/english').json()
    assert state['completed']==[payload['lesson_id']] and state['next_lesson_id']!=payload['lesson_id']
    assert client.post('/api/study/plans',json=values(key='other'),headers=headers).status_code==409
    replacement=activate(client,headers,key='replace',previous=plan['id'],level='B1')
    assert replacement['id']!=plan['id']
    # An uncertain retry of the original attempt is still safe after replacement.
    assert client.post('/api/study/attempts',json=payload,headers=headers).json()['id']==saved.json()['id']
    assert client.post('/api/study/attempts',json=attempt(plan,key='late'),headers=headers).status_code==409
    historical=client.get('/api/study/state/english?plan_id='+plan['id']).json()
    assert historical['plan']['archived'] and historical['attempts'][0]['snapshot']['title']
    assert historical['completed']==[payload['lesson_id']]
    assert client.get('/api/tasks').json()['items']==[]


def test_backend_v1_plan_can_be_replaced_with_v2_without_rewriting_history(client,mailbox):
    headers=h(client,mailbox)
    old=activate(client,headers,course='java-backend',level='foundation',key='backend-old')
    assert old['version']=='v1' and len(old['lesson_ids'])==8
    payload=values(course='java-backend',level='foundation',key='backend-new',previous=old['id'])|{'version':'v2'}
    response=client.post('/api/study/plans',json=payload,headers=headers)
    assert response.status_code==201,response.text
    new=response.json()
    assert new['version']=='v2' and len(new['lesson_ids'])==12
    history=client.get('/api/study/state/java-backend?plan_id='+old['id']).json()
    assert history['plan']['version']=='v1' and history['plan']['archived']
    assert len(history['plan']['lesson_ids'])==8


def test_server_grading_and_evidence_are_private_and_immutable(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    payload=attempt(plan);payload['answers'][0]='wrong'
    result=client.post('/api/study/attempts',json=payload,headers=headers).json()
    assert not result['passed'] and result['score']==2 and result['feedback'][0]['explanation']
    assert client.get('/api/study/state/english').json()['next_lesson_id']==payload['lesson_id']
    for change in [dict(answers=[]),dict(evidence=''),dict(self_checks=[]),dict(portfolio_url='javascript:alert(1)'),dict(date=(local_date('Asia/Almaty')+timedelta(days=1)).isoformat())]:
        assert client.post('/api/study/attempts',json={**attempt(plan,key='invalid'),**change},headers=headers).status_code==422
    other=h(client,mailbox,'two@example.com')
    assert client.get('/api/study/state/english').json()['plans']==[]
    assert client.get('/api/study/state/english?plan_id='+plan['id']).status_code==404
    assert client.post('/api/study/attempts',json=attempt(plan,key='attack'),headers=other).status_code==404


def test_pending_retry_uses_full_progress_not_history_page(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    failed=attempt(plan);failed['answers'][0]='wrong'
    assert client.post('/api/study/attempts',json=failed,headers=headers).json()['passed'] is False
    state=client.get('/api/study/state/english?history_offset=20').json()
    assert state['attempts']==[]
    assert state['pending_retry_lesson_id']==failed['lesson_id']
    assert client.post('/api/study/attempts',json=attempt(plan,key='passed-later'),headers=headers).json()['passed']
    assert client.get('/api/study/state/english').json()['pending_retry_lesson_id'] is None


def test_vocabulary_due_review_retry_and_stale_write(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    assert client.get('/api/study/cards/english').json()['items']==[]
    client.post('/api/study/attempts',json=attempt(plan),headers=headers)
    cards=client.get('/api/study/cards/english').json()['items'];assert len(cards)==4
    card=cards[0]
    payload=dict(course_id='english',version='v1',card_id=card['id'],rating='remembered',expected_review_id=None,create_key='review')
    result=client.post('/api/study/reviews',json=payload,headers=headers)
    assert result.status_code==201
    assert result.json()['due_date']==(local_date('Asia/Almaty')+timedelta(days=1)).isoformat()
    assert client.post('/api/study/reviews',json=payload,headers=headers).json()['id']==result.json()['id']
    assert len(client.get('/api/study/cards/english').json()['items'])==3
    assert client.post('/api/study/reviews',json={**payload,'create_key':'stale'},headers=headers).status_code==409
    other=h(client,mailbox,'two@example.com')
    assert client.post('/api/study/reviews',json=payload,headers=other).status_code==422


def test_daily_links_respect_plan_days_and_keep_plans_separate(client,mailbox):
    headers=h(client,mailbox);p=activate(client,headers)
    java=activate(client,headers,course='java',level='beginner',key='java')
    today=local_date('Asia/Almaty');due=today
    while due.weekday() not in (0,2,4):due+=timedelta(days=1)
    items=client.get('/api/study/day?date='+due.isoformat()).json()['items']
    assert {i['plan_id'] for i in items}=={p['id'],java['id']}
    assert all('lesson_id' in i and i['date']==due.isoformat() for i in items)
    assert client.get('/api/study/day?date='+(today-timedelta(days=1)).isoformat()).json()['items']==[]
    off=due
    while off.weekday() in (0,2,4):off+=timedelta(days=1)
    assert client.get('/api/study/day?date='+off.isoformat()).json()['items']==[]


def test_diagnostic_is_limited_and_does_not_forge_a_plan(client,mailbox):
    headers=h(client,mailbox)
    r=client.get('/api/study/diagnostic').json()
    assert len(r['questions'])==6 and r['limitation']
    result=client.post('/api/study/diagnostic',json={'answers':['wrong']*6},headers=headers)
    assert result.status_code==200 and result.json()['level']=='A2'
    assert result.json()['below_scope'] is True
    assert client.get('/api/study/state/english').json()['active_plan'] is None


def test_normalized_answers_and_saved_snapshot_survive_content_change(client,mailbox,monkeypatch):
    headers=h(client,mailbox);p=activate(client,headers)
    payload=attempt(p);payload['answers']=['  '+a.upper()+'  ' for a in payload['answers']]
    result=client.post('/api/study/attempts',json=payload,headers=headers).json()
    assert result['passed']
    from app.routes import study
    original=study.course
    def changed(*args,**kwargs):
        c=original(*args,**kwargs);c['lessons'][0]['title']='Changed future title';return c
    monkeypatch.setattr(study,'course',changed)
    history=client.get('/api/study/state/english').json()['attempts']
    assert history[0]['snapshot']['title']==result['snapshot']['title']
    assert history[0]['snapshot']['title']!='Changed future title'
    assert client.get('/api/study/state/english?history_offset=1').json()['attempts']==[]


def test_reviews_advance_intervals_and_use_server_local_date(client,mailbox,monkeypatch):
    headers=h(client,mailbox);p=activate(client,headers)
    client.post('/api/study/attempts',json=attempt(p),headers=headers)
    card=client.get('/api/study/cards/english').json()['items'][0]
    data=dict(course_id='english',card_id=card['id'],rating='remembered',expected_review_id=None,create_key='first')
    first=client.post('/api/study/reviews',json=data,headers=headers).json()
    from app.routes import study
    tomorrow=local_date('Asia/Almaty')+timedelta(days=1)
    monkeypatch.setattr(study,'local_date',lambda zone:tomorrow)
    second=client.post('/api/study/reviews',json={**data,'expected_review_id':first['id'],'create_key':'second'},headers=headers).json()
    assert second['due_date']==(tomorrow+timedelta(days=3)).isoformat()
    assert client.post('/api/study/reviews',json={**data,'expected_review_id':second['id'],'create_key':'too-soon'},headers=headers).status_code==422


def draft_values(plan):
    course=next(c for c in COURSES if c['id']==plan['course_id'])
    lesson=next(l for l in course['lessons'] if l['id']==plan['lesson_ids'][0])
    return dict(expected_revision=None,answers=['']*len(lesson['quiz']),evidence='Мои незаконченные заметки.',
                self_checks=[False]*len(lesson['rubric']),date=local_date('Asia/Almaty').isoformat(),
                portfolio_url='',create_key='draft-attempt-1')


def test_private_study_draft_survives_reload_and_is_cleared_by_confirmed_attempt(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    path=f"/api/study/drafts/{plan['id']}/{plan['lesson_ids'][0]}"
    data=draft_values(plan)
    assert client.put(path,json=data).status_code==403
    saved=client.put(path,json=data,headers=headers)
    assert saved.status_code==200,saved.text
    assert saved.json()['revision']==1
    assert saved.json()['content']['evidence']==data['evidence']
    assert client.get('/api/study/drafts/english').json()['items'][0]['id']==saved.json()['id']
    invalid={**data,'answers':[],'create_key':'other'}
    assert client.put(path,json=invalid,headers=headers).status_code==422
    other=h(client,mailbox,'other@example.com')
    assert client.get('/api/study/drafts/english').json()['items']==[]
    assert client.put(path,json=data,headers=other).status_code==404
    headers={'X-CSRF-Token':client.post('/api/auth/login',json={'email':'one@example.com','password':'correct horse battery staple'}).json()['csrf_token']}
    attempt_data=attempt(plan,key=data['create_key'])
    attempt_data['expected_draft_revision']=saved.json()['revision']
    assert client.post('/api/study/attempts',json=attempt_data,headers=headers).status_code==201
    assert client.get('/api/study/drafts/english').json()['items']==[]
    assert client.put(path,json=data,headers=headers).status_code==409


def test_stale_attempt_cannot_remove_newer_draft_from_another_device(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    path=f"/api/study/drafts/{plan['id']}/{plan['lesson_ids'][0]}"
    data=draft_values(plan)
    first=client.put(path,json=data,headers=headers).json()
    newer={**data,'expected_revision':first['revision'],'evidence':'Более свежий текст с другого устройства.'}
    second=client.put(path,json=newer,headers=headers).json()
    old_attempt=attempt(plan,key=data['create_key'])
    old_attempt['expected_draft_revision']=first['revision']
    response=client.post('/api/study/attempts',json=old_attempt,headers=headers)
    assert response.status_code==409
    current=client.get('/api/study/drafts/english').json()['items'][0]
    assert current['revision']==second['revision']
    assert current['content']['evidence']==newer['evidence']
    fresh=attempt(plan,key='newer-attempt')
    fresh['expected_draft_revision']=second['revision']
    assert client.post('/api/study/attempts',json=fresh,headers=headers).status_code==201
    assert client.get('/api/study/drafts/english').json()['items']==[]


def test_study_draft_revision_retry_and_archived_copy(client,mailbox):
    headers=h(client,mailbox);plan=activate(client,headers)
    path=f"/api/study/drafts/{plan['id']}/{plan['lesson_ids'][0]}"
    data=draft_values(plan)
    first=client.put(path,json=data,headers=headers).json()
    assert client.put(path,json=data,headers=headers).json()['revision']==1
    changed={**data,'evidence':'Изменённый собственный черновик.'}
    assert client.put(path,json=changed,headers=headers).status_code==409
    second=client.put(path,json={**changed,'expected_revision':1},headers=headers)
    assert second.status_code==200 and second.json()['revision']==2
    replacement=activate(client,headers,key='replacement',previous=plan['id'],level='B1')
    assert replacement['id']!=plan['id']
    assert client.put(path,json={**changed,'expected_revision':2},headers=headers).status_code==409
    assert client.get('/api/study/drafts/english').json()['items'][0]['content']['evidence']==changed['evidence']
