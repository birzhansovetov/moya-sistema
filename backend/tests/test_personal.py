from test_spheres import sign_in


def entry():
    return dict(kind='diary', title='', body='Сегодня я закончил важное дело.', date='2026-10-10', mood='good', activity='other', completed=False, impression='', create_key='journal-1')


def test_personal_private_crud_and_retry(client, mailbox):
    assert client.get('/api/personal/entries').status_code == 401
    headers = {'X-CSRF-Token': sign_in(client, mailbox, 'one@example.com')}
    payload = entry()
    assert client.post('/api/personal/entries', json=payload).status_code == 403
    response = client.post('/api/personal/entries', json=payload, headers=headers)
    assert response.status_code == 201
    item = response.json()
    assert item['body'] == payload['body']
    assert client.post('/api/personal/entries', json=payload, headers=headers).json()['id'] == item['id']
    assert client.post('/api/personal/entries', json={**payload, 'body': 'Другое'}, headers=headers).status_code == 409
    changed = client.patch('/api/personal/entries/'+item['id'], json={**payload, 'body': 'Новая мысль'}, headers=headers)
    assert changed.json()['body'] == 'Новая мысль'
    assert client.get('/api/personal/entries?q=НОВАЯ').json()['total'] == 1
    assert client.delete('/api/personal/entries/'+item['id'], headers=headers).status_code == 204
    assert client.get('/api/personal/entries').json()['total'] == 0
    assert client.get('/api/personal/entries?deleted=true').json()['items'][0]['id'] == item['id']
    assert client.post('/api/personal/entries/'+item['id']+'/restore', headers=headers).status_code == 200
    other = {'X-CSRF-Token': sign_in(client, mailbox, 'two@example.com')}
    assert client.get('/api/personal/entries').json()['total'] == 0
    for method, suffix, body in [('GET','',None),('PATCH','',payload),('DELETE','',None),('POST','/restore',None)]:
        assert client.request(method, '/api/personal/entries/'+item['id']+suffix, json=body, headers=other).status_code == 404


def test_personal_ideas_dates_validation_and_filters(client, mailbox):
    headers = {'X-CSRF-Token': sign_in(client, mailbox, 'one@example.com')}
    base = entry()
    for fields in [{'date': None}, {'body':'', 'title':''}, {'mood':'random'}, {'kind':'random'}]:
        assert client.post('/api/personal/entries', json={**base, **fields}, headers=headers).status_code == 422
    idea = {**base, 'kind':'experiment', 'date': None, 'title':'Попробовать рисование', 'body':'20 минут', 'mood':None}
    assert client.post('/api/personal/entries', json=idea, headers=headers).status_code == 201
    event = {**base, 'kind':'event', 'title':'Прогулка с другом', 'date':'2026-10-11', 'create_key':'event-1', 'activity':'meeting', 'mood':None}
    saved = client.post('/api/personal/entries', json=event, headers=headers).json()
    assert client.get('/api/personal/entries?kind=event&start=2026-10-11&end=2026-10-11').json()['items'][0]['id'] == saved['id']
    assert client.get('/api/personal/entries?start=2026-10-12&end=2026-10-11').status_code == 422
    result = client.get('/api/personal/entries?limit=1&offset=1').json()
    assert result['total'] == 2 and len(result['items']) == 1
    done = client.patch('/api/personal/entries/'+saved['id'], json={**event,'completed':True,'impression':'Хочу повторить'}, headers=headers).json()
    assert done['completed'] and done['impression'] == 'Хочу повторить'


def test_calendar_includes_only_owned_dated_events_and_never_diary_content(client,mailbox):
    h={'X-CSRF-Token':sign_in(client,mailbox,'one@example.com')}
    diary=entry()
    assert client.post('/api/personal/entries',json=diary,headers=h).status_code==201
    event={**diary,'kind':'event','title':'Встреча','body':'Приватные детали','impression':'Приватное впечатление','create_key':'event'}
    saved=client.post('/api/personal/entries',json=event,headers=h).json()
    client.post('/api/personal/entries',json={**event,'kind':'experiment','date':None,'create_key':'idea'},headers=h)
    path='/api/calendar?start=2026-10-10&end=2026-10-10'
    data=client.get(path).json()
    assert data['items']==[]
    assert data['personal_items']==[{'id':saved['id'],'title':'Встреча','date':'2026-10-10','kind':'event','completed':False}]
    assert 'Приватные' not in str(data) and diary['body'] not in str(data)
    client.delete('/api/personal/entries/'+saved['id'],headers=h)
    assert client.get(path).json()['personal_items']==[]
    client.post('/api/personal/entries/'+saved['id']+'/restore',headers=h)
    sign_in(client,mailbox,'two@example.com')
    assert client.get(path).json()['personal_items']==[]
