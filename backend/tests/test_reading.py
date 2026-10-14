from test_spheres import sign_in


def book():
    return dict(title='Тестовая книга', author='Автор', pages=100, current_page=10, daily_pages=15, status='reading', start_date='2026-10-01', end_date=None, cover_url='', final_impression='', create_key='book-1')


def log(**changes):
    return {**dict(date='2026-10-09', page=30, chapter='', text='', reflection={}, create_key='log-1'), **changes}


def test_reading_progress_history_free_text_and_recovery(client, mailbox):
    h={'X-CSRF-Token':sign_in(client,mailbox,'reader@example.com')}
    response=client.post('/api/reading/books',json=book(),headers=h)
    assert response.status_code==201
    saved=response.json(); bid=saved['id']; path=f'/api/reading/books/{bid}'
    assert saved['current_page']==10 and saved['next_page']==25
    assert client.post('/api/reading/books',json=book(),headers=h).json()['id']==bid
    first=client.post(path+'/logs',json=log(),headers=h).json()
    assert client.get(path).json()['current_page']==30
    # Backdated notes do not move the current bookmark backwards.
    assert client.post(path+'/logs',json=log(date='2026-10-08',page=20,create_key='older'),headers=h).status_code==201
    assert client.get(path).json()['current_page']==30
    assert client.post(path+'/logs',json=log(),headers=h).json()['id']==first['id']
    text=client.post(path+'/logs',json=log(page=None,text='Я сам записываю впечатления.',create_key='text'),headers=h)
    assert text.status_code==201 and text.json()['reflection']=={}
    assert client.get(path).json()['current_page']==30
    assert client.patch(path+'/logs/'+first['id'],json=log(page=35),headers=h).status_code==200
    assert client.get(path).json()['current_page']==35
    assert client.delete(path+'/logs/'+first['id'],headers=h).status_code==204
    assert client.get(path).json()['current_page']==20
    assert client.post(path+'/logs/'+first['id']+'/restore',headers=h).status_code==200
    assert client.get(path).json()['current_page']==35
    assert client.get(path+'/logs?q=ВПЕЧАТЛЕНИЯ').json()['total']==1
    assert client.delete(path,headers=h).status_code==204
    assert client.get('/api/reading/books').json()['total']==0
    assert client.post(path+'/restore',headers=h).status_code==200
    assert client.get(path).json()['current_page']==35


def test_reading_validates_pages_and_keeps_other_accounts_out(client, mailbox):
    h={'X-CSRF-Token':sign_in(client,mailbox,'one@example.com')}
    assert client.post('/api/reading/books',json=book()).status_code==403
    assert client.post('/api/reading/books',json={**book(),'current_page':101},headers=h).status_code==422
    saved=client.post('/api/reading/books',json=book(),headers=h).json();path='/api/reading/books/'+saved['id']
    for changes in [{'page':101},{'page':None,'text':'','chapter':''},{'reflection':{'unknown':'text'}},{'date':'9999-01-01'}]:
        assert client.post(path+'/logs',json=log(**changes),headers=h).status_code==422
    note=client.post(path+'/logs',json=log(),headers=h).json()
    assert client.patch(path,json={**book(),'pages':25},headers=h).status_code==422
    other={'X-CSRF-Token':sign_in(client,mailbox,'two@example.com')}
    assert client.get('/api/reading/books').json()['total']==0
    for method,suffix,payload in [('GET','',None),('PATCH','',book()),('DELETE','',None),('POST','/restore',None),('GET','/logs',None),('POST','/logs',log()),('PATCH','/logs/'+note['id'],log()),('DELETE','/logs/'+note['id'],None),('POST','/logs/'+note['id']+'/restore',None)]:
        assert client.request(method,path+suffix,json=payload,headers=other).status_code==404


def test_title_only_book_can_be_recorded_without_inventing_page_count(client, mailbox):
    headers={'X-CSRF-Token':sign_in(client,mailbox,'title-only@example.com')}
    saved=client.post('/api/reading/books',json={'title':'Книга вне каталога','status':'reading','create_key':'title-only'},headers=headers)
    assert saved.status_code==201,saved.text
    assert saved.json()['pages']==0 and saved.json()['next_page'] is None
    path='/api/reading/books/'+saved.json()['id']
    assert client.post(path+'/logs',json=log(page=None,text='Начал читать',create_key='note'),headers=headers).status_code==201
    assert client.post(path+'/logs',json=log(page=10,create_key='page'),headers=headers).status_code==422
    updated=client.patch(path,json={'title':'Книга вне каталога','pages':200,'status':'reading'},headers=headers)
    assert updated.status_code==200 and updated.json()['next_page']==10
