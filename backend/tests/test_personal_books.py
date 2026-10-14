from io import BytesIO
from importlib.resources import files
from zipfile import ZipFile, ZIP_DEFLATED

from pypdf import PdfWriter

from test_spheres import sign_in


class MemoryStore:
    def __init__(self):
        self.objects = {}
        self.fail_put = False

    def put(self, key, data, content_type):
        if self.fail_put:
            raise OSError('store unavailable')
        self.objects[key] = data

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)


def pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def upload(client, headers, name, data, key):
    return client.post('/api/reading/books/uploads', headers=headers,
                       data={'create_key': key}, files={'file': (name, data)})


def login(client, email):
    response = client.post('/api/auth/login', json={'email': email, 'password': 'correct horse battery staple'})
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json()['csrf_token']}


def test_import_formats_and_private_reading(client, mailbox):
    store = MemoryStore()
    client.app.state.book_store = store
    first = {'X-CSRF-Token': sign_in(client, mailbox, 'personal-file-one@example.com')}
    epub = files('app.content').joinpath('ebooks', 'chekhov-chameleon.epub').read_bytes()
    fb2 = b'<?xml version="1.0" encoding="UTF-8"?><FictionBook><description><title-info><book-title>Test</book-title></title-info></description><body><section><title><p>Start</p></title><p>Hello world.</p></section></body></FictionBook>'
    second = None
    for name, content, fmt in [('story.epub', epub, 'epub'), ('story.fb2', fb2, 'fb2'), ('story.pdf', pdf_bytes(), 'pdf')]:
        response = upload(client, first, name, content, name)
        assert response.status_code == 201, response.text
        item = response.json()
        assert item['format'] == fmt and item['title']
        same = upload(client, first, name, content, name)
        assert same.status_code == 200 and same.json()['id'] == item['id']
        path = f"/api/reading/books/uploads/{item['id']}"
        assert client.get(path + '/file').content == content
        if fmt != 'pdf':
            text = client.get(path + '/read').json()
            assert text['paragraphs'] and text['chapters']
        else:
            assert client.get(path + '/file', headers={'Range': 'bytes=0-4'}).status_code == 206
        assert client.put(path + '/reader-state', json={'location': {'format': fmt, **({'page': 0} if fmt == 'pdf' else {'chapter': 0, 'position': 0})}, 'bookmarks': []}, headers=first).status_code == 200
        second = ({'X-CSRF-Token': sign_in(client, mailbox, 'personal-file-two@example.com')}
                  if second is None else login(client, 'personal-file-two@example.com'))
        for suffix in ('', '/file', '/read', '/reader-state'):
            assert client.get(path + suffix).status_code == 404
        assert client.delete(path, headers=second).status_code == 404
        first = login(client, 'personal-file-one@example.com')
        assert client.get(path + '/reader-state').json()['location']['format'] == fmt


def test_import_rejects_invalid_and_rolls_back(client, mailbox):
    store = MemoryStore()
    client.app.state.book_store = store
    headers = {'X-CSRF-Token': sign_in(client, mailbox, 'invalid-files@example.com')}
    for name, content in [('fake.epub', b'not a zip'), ('fake.fb2', b'<FictionBook><body>'), ('fake.pdf', b'%PDF-1.7\nnot a pdf'), ('file.txt', b'hello'), ('large.fb2', b'x' * (16 * 1024 * 1024))]:
        assert upload(client, headers, name, content, name).status_code in (400, 413, 422)
    assert not store.objects
    bomb = BytesIO()
    with ZipFile(bomb, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('mimetype', 'application/epub+zip')
        archive.writestr('huge.xhtml', b'A' * (51 * 1024 * 1024))
    assert upload(client, headers, 'bomb.epub', bomb.getvalue(), 'bomb').status_code == 400
    store.fail_put = True
    response = upload(client, headers, 'valid.pdf', pdf_bytes(), 'storage-failure')
    assert response.status_code == 503
    assert client.get('/api/reading/books/uploads').json()['items'] == []


def test_missing_object_and_delete(client, mailbox):
    store = MemoryStore()
    client.app.state.book_store = store
    headers = {'X-CSRF-Token': sign_in(client, mailbox, 'missing-personal-book@example.com')}
    created = upload(client, headers, 'book.pdf', pdf_bytes(), 'book').json()
    path = f"/api/reading/books/uploads/{created['id']}"
    store.objects.clear()
    assert client.get(path + '/file').status_code == 409
    assert client.delete(path, headers=headers).status_code == 204
    assert client.get(path).status_code == 404
