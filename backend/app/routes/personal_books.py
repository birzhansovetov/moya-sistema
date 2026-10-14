"""Authenticated personal-library files; no object URL leaves this API."""

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.book_storage import MAX_BOOK_BYTES, MIME, InvalidBook, inspect_book
from app.db import get_db, utc_now
from app.models import ReaderState, UploadedBook, User
from app.routes.reading import ReaderStateValues


router = APIRouter(prefix='/api/reading/books/uploads', tags=['reading'])


def store_from(request: Request):
    store = request.app.state.book_store
    if store is None:
        raise HTTPException(503, 'Загрузка личных книг пока не настроена')
    return store


def owned(db: Session, owner: str, file_id: str) -> UploadedBook:
    item = db.get(UploadedBook, file_id)
    if item is None or item.user_id != owner:
        raise HTTPException(404, 'Книга не найдена')
    if not item.object_key.startswith(f'{owner}/'):
        raise HTTPException(409, 'Файл нужно загрузить заново')
    return item


def serial(item: UploadedBook) -> dict:
    return {'id': item.id, 'title': item.title, 'format': item.format,
            'original_filename': item.original_filename, 'size_bytes': item.size_bytes,
            'page_count': item.page_count, 'created_at': item.created_at.isoformat()}


def read_bytes(store, item: UploadedBook) -> bytes:
    try:
        data = store.get(item.object_key)
    except KeyError:
        raise HTTPException(409, 'Файл отсутствует в хранилище. Загрузите его заново.') from None
    except Exception:
        raise HTTPException(503, 'Не удалось открыть файл. Повторите позже.') from None
    if len(data) != item.size_bytes or hashlib.sha256(data).hexdigest() != item.checksum:
        raise HTTPException(409, 'Сохранённый файл повреждён. Загрузите его заново.')
    return data


@router.get('/status')
def storage_status(request: Request, user: User = Depends(get_current_user)):
    return {'enabled': request.app.state.book_store is not None, 'formats': ['epub', 'fb2', 'pdf'], 'max_bytes': MAX_BOOK_BYTES}


@router.get('')
def list_uploads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(UploadedBook).where(UploadedBook.user_id == user.id).order_by(UploadedBook.created_at.desc(), UploadedBook.id)).all()
    return {'items': [serial(item) for item in items]}


@router.post('', status_code=201)
async def upload_book(request: Request, file: UploadFile = File(...), create_key: str = Form(...),
                      context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    store = store_from(request)
    if not create_key or len(create_key) > 100:
        raise HTTPException(422, 'Неверный ключ сохранения')
    filename = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1][:200]
    data = await file.read(MAX_BOOK_BYTES + 1)
    if len(data) > MAX_BOOK_BYTES:
        raise HTTPException(413, 'Книга превышает 15 МБ')
    try:
        parsed = inspect_book(filename, data)
    except InvalidBook as exc:
        raise HTTPException(400, str(exc)) from exc
    checksum = hashlib.sha256(data).hexdigest()
    query = select(UploadedBook).where(UploadedBook.user_id == context.user.id, UploadedBook.create_key == create_key)
    existing = db.scalar(query)
    if existing:
        if existing.checksum != checksum or existing.original_filename != filename:
            raise HTTPException(409, 'Этот ключ уже использован для другой книги')
        return Response(content=json.dumps(serial(existing)), media_type='application/json', status_code=200)
    title = (parsed.title or filename.rsplit('.', 1)[0] or 'Книга').strip()[:200]
    item_id = str(uuid.uuid4())
    key = f'{context.user.id}/{item_id}.{parsed.format}'
    item = UploadedBook(id=item_id, user_id=context.user.id, title=title, original_filename=filename,
                        format=parsed.format, object_key=key, checksum=checksum, size_bytes=len(data),
                        page_count=parsed.page_count, create_key=create_key, created_at=utc_now())
    try:
        store.put(key, data, MIME[parsed.format])
    except Exception:
        raise HTTPException(503, 'Не удалось сохранить файл. Повторите попытку.') from None
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        try:
            store.delete(key)
        except Exception:
            pass
        existing = db.scalar(query)
        if existing and existing.checksum == checksum and existing.original_filename == filename:
            return Response(content=json.dumps(serial(existing)), media_type='application/json', status_code=200)
        raise HTTPException(409, 'Ключ сохранения уже использован') from None
    except Exception:
        db.rollback()
        try:
            store.delete(key)
        except Exception:
            pass
        raise
    return serial(item)


@router.get('/{file_id}')
def get_upload(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serial(owned(db, user.id, file_id))


@router.get('/{file_id}/read')
def read_upload(file_id: str, request: Request, offset: int = 0,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned(db, user.id, file_id)
    if item.format == 'pdf':
        raise HTTPException(422, 'PDF открывается по страницам')
    if offset < 0:
        raise HTTPException(422, 'Неверное место чтения')
    parsed = inspect_book(item.original_filename, read_bytes(store_from(request), item))
    end = min(offset + 60, len(parsed.paragraphs))
    return {'paragraphs': parsed.paragraphs[offset:end], 'chapters': parsed.chapters,
            'total': len(parsed.paragraphs), 'next_offset': end if end < len(parsed.paragraphs) else None,
            'checksum': item.checksum}


@router.get('/{file_id}/file')
def file_bytes(file_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned(db, user.id, file_id)
    data = read_bytes(store_from(request), item)
    header = request.headers.get('range')
    start, end, code = 0, len(data) - 1, 200
    if header:
        try:
            unit, extent = header.split('=', 1)
            first, last = extent.split('-', 1)
            if unit != 'bytes' or not first.isdigit() or (last and not last.isdigit()):
                raise ValueError
            start = int(first)
            end = min(int(last), len(data) - 1) if last else len(data) - 1
            if start > end or start >= len(data):
                raise ValueError
            code = 206
        except ValueError:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{len(data)}'})
    headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
               'Accept-Ranges': 'bytes', 'Content-Disposition': f'{"inline" if item.format == "pdf" else "attachment"}; filename="book.{item.format}"'}
    if code == 206:
        headers['Content-Range'] = f'bytes {start}-{end}/{len(data)}'
    return Response(data[start:end + 1], status_code=code, media_type=MIME[item.format], headers=headers)


def reader_record(db: Session, user_id: str, item: UploadedBook) -> ReaderState | None:
    return db.scalar(select(ReaderState).where(ReaderState.user_id == user_id, ReaderState.content_id == f'personal:{item.id}'))


@router.get('/{file_id}/reader-state')
def get_position(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned(db, user.id, file_id)
    state = reader_record(db, user.id, item)
    return {'location': state.location if state and state.checksum == item.checksum else None,
            'bookmarks': state.bookmarks if state and state.checksum == item.checksum else [], 'checksum': item.checksum}


@router.put('/{file_id}/reader-state')
def save_position(file_id: str, payload: ReaderStateValues, request: Request,
                  context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, file_id)
    parsed = inspect_book(item.original_filename, read_bytes(store_from(request), item))
    locations = ([payload.location] if payload.location else []) + payload.bookmarks
    for location in locations:
        if location.format != item.format:
            raise HTTPException(422, 'Неверный формат закладки')
        if item.format == 'pdf':
            if location.page >= (parsed.page_count or 0):
                raise HTTPException(422, 'Страница вне книги')
        elif location.position >= len(parsed.paragraphs) or location.chapter >= len(parsed.chapters):
            raise HTTPException(422, 'Место чтения вне книги')
    state = reader_record(db, context.user.id, item)
    if state is None:
        state = ReaderState(user_id=context.user.id, content_id=f'personal:{item.id}', checksum=item.checksum)
        db.add(state)
    state.checksum = item.checksum
    state.location = payload.location.model_dump() if payload.location else None
    state.bookmarks = [value.model_dump() for value in payload.bookmarks]
    state.updated_at = utc_now()
    db.commit()
    return {'location': state.location, 'bookmarks': state.bookmarks, 'checksum': state.checksum}


@router.delete('/{file_id}', status_code=204)
def remove_upload(file_id: str, request: Request, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, file_id)
    try:
        store_from(request).delete(item.object_key)
    except Exception:
        raise HTTPException(503, 'Не удалось удалить файл. Повторите попытку.') from None
    state = reader_record(db, context.user.id, item)
    if state:
        db.delete(state)
    db.delete(item)
    db.commit()
    return Response(status_code=204)
