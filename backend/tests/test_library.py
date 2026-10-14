def test_materials_are_authenticated_and_complete(client,mailbox):
    from test_spheres import sign_in
    assert client.get('/api/library/guides?area=personal').status_code==401
    sign_in(client,mailbox,'one@example.com')
    for area in ['personal','reading','finance','sport']:
        data=client.get('/api/library/guides?area='+area)
        assert data.status_code==200
        assert data.json()['items']
        for item in data.json()['items']:
            assert item['steps'] and item['example'] and item['check'] and item['version']
    assert client.get('/api/library/guides?area=unknown').status_code==422
    suggestions=client.get('/api/library/books').json()['items']
    assert len(suggestions)>=8
    assert all(item['source'].startswith('https://') and item['questions'] and item['author'] for item in suggestions)
    assert any(item['id'] == 'chekhov-cherry-orchard-mybook' and item['source'] == 'https://mybook.ru/author/anton-pavlovich-chehov/vishnevyj-sad/' for item in suggestions)


def test_personal_guides_include_a_change_of_plan_path(client, mailbox):
    from test_spheres import sign_in
    sign_in(client, mailbox, 'guide@example.com')
    items = client.get('/api/library/guides?area=personal').json()['items']
    guide = next(item for item in items if item['id'] == 'personal-change')
    assert len(guide['steps']) >= 4
    assert any('измен' in step.lower() for step in guide['steps'])
    assert any('подош' in step.lower() for step in guide['steps'])


def test_locally_licensed_books_can_be_read_and_downloaded(client, mailbox):
    from test_spheres import sign_in
    assert client.get('/api/library/books/chekhov-chameleon/download').status_code == 401
    sign_in(client, mailbox, 'book@example.com')
    books = client.get('/api/library/books').json()['items']
    local = [item for item in books if item['available_offline']]
    assert len(local) == len(books) == 12
    for item in local:
        response = client.get(f"/api/library/books/{item['id']}/download")
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/epub+zip'
        assert response.content[:2] == b'PK'
        reading = client.get(f"/api/library/books/{item['id']}/read")
        assert reading.status_code == 200
        assert len(reading.json()['paragraphs']) >= 20
        assert reading.json()['total'] >= len(reading.json()['paragraphs'])
    long_book = client.get('/api/library/books/turgenev-hunters-notes/read').json()
    assert long_book['next_offset'] == 60
    assert client.get('/api/library/books/turgenev-hunters-notes/read?offset=60').json()['paragraphs'][0] != long_book['paragraphs'][0]
    assert client.get('/api/library/books/unknown/download').status_code == 404
