import hashlib
import json
from datetime import date as DateValue
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db, utc_now
from app.models import ReadingBook, ReadingLog, ReaderState, User
from app.routes.library import book_checksum, book_paragraphs
from app.tasks import local_date

router = APIRouter(prefix='/api/reading/books', tags=['reading'])
Status = Literal['want', 'reading', 'finished', 'paused']
ReflectionKey = Literal['read', 'understood', 'felt', 'struck', 'connection', 'apply']


class BookValues(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(default='', max_length=160)
    pages: int = Field(default=0, ge=0, le=100000)
    daily_pages: int = Field(default=10, ge=1, le=10000)
    status: Status = 'want'
    start_date: DateValue | None = None
    end_date: DateValue | None = None
    cover_url: str = Field(default='', max_length=2000)
    final_impression: str = Field(default='', max_length=20000)

    @model_validator(mode='after')
    def clean(self):
        self.title, self.author, self.final_impression = self.title.strip(), self.author.strip(), self.final_impression.strip()
        if not self.title:
            raise ValueError('Укажите название книги')
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('Дата окончания раньше начала')
        if self.cover_url and (urlparse(self.cover_url).scheme != 'https' or not urlparse(self.cover_url).netloc or urlparse(self.cover_url).username):
            raise ValueError('Обложка должна быть доступна по HTTPS-ссылке без пароля')
        return self


class BookCreate(BookValues):
    current_page: int = Field(default=0, ge=0)
    create_key: str = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def page_bound(self):
        if self.pages and self.current_page > self.pages:
            raise ValueError('Текущая страница больше числа страниц')
        if not self.pages and self.current_page:
            raise ValueError('Укажите число страниц перед отметкой прогресса')
        return self


class LogValues(BaseModel):
    date: DateValue
    page: int | None = Field(default=None, ge=0)
    chapter: str = Field(default='', max_length=200)
    text: str = Field(default='', max_length=20000)
    reflection: dict[ReflectionKey, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def clean(self):
        self.chapter, self.text = self.chapter.strip(), self.text.strip()
        self.reflection = {key: value.strip() for key, value in self.reflection.items() if value.strip()}
        if any(len(value) > 5000 for value in self.reflection.values()):
            raise ValueError('Ответ должен быть не длиннее 5000 символов')
        if self.page is None and not self.chapter and not self.text and not self.reflection:
            raise ValueError('Добавьте страницу, главу или свою заметку')
        return self


class LogCreate(LogValues):
    create_key: str = Field(min_length=1, max_length=100)


class ReaderLocation(BaseModel):
    format: Literal['epub', 'fb2']
    chapter: int = Field(ge=0, le=10000)
    position: int = Field(ge=0, le=10000000)


class PdfReaderLocation(BaseModel):
    format: Literal['pdf']
    page: int = Field(ge=0, le=100000)


class ReaderStateValues(BaseModel):
    location: ReaderLocation | PdfReaderLocation | None = None
    bookmarks: list[ReaderLocation | PdfReaderLocation] = Field(default_factory=list, max_length=100)


def owned(db, user_id, book_id):
    item = db.get(ReadingBook, book_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(404, 'Книга не найдена')
    return item


def owned_log(db, book_id, log_id):
    item = db.get(ReadingLog, log_id)
    if item is None or item.book_id != book_id:
        raise HTTPException(404, 'Запись чтения не найдена')
    return item


def serialize_book(db, item):
    latest = db.scalar(select(ReadingLog).where(ReadingLog.book_id == item.id, ReadingLog.deleted_at.is_(None), ReadingLog.page.is_not(None)).order_by(ReadingLog.date.desc(), ReadingLog.created_at.desc(), ReadingLog.id).limit(1))
    current = latest.page if latest else item.initial_page
    return {**{key: getattr(item, key) for key in BookValues.model_fields}, 'id': item.id, 'current_page': current,
            'next_page': min(item.pages, current + item.daily_pages) if item.pages else None, 'deleted': item.deleted_at is not None}


def serialize_log(item):
    return {**{key: getattr(item, key) for key in LogValues.model_fields}, 'id': item.id, 'book_id': item.book_id, 'deleted': item.deleted_at is not None}


def create_once(db, model, scope, create_key, data):
    fingerprint = hashlib.sha256(json.dumps(data, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    query = select(model).filter_by(**scope, create_key=create_key)

    def replay(item):
        if item.create_fingerprint != fingerprint:
            raise HTTPException(409, 'Ключ сохранения уже использован для другой записи')
        if item.deleted_at:
            raise HTTPException(409, 'Запись удалена. Её можно восстановить.')
        return item

    existing = db.scalar(query)
    if existing:
        return replay(existing)
    item = model(**scope, **data, create_key=create_key, create_fingerprint=fingerprint)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query)
        if existing:
            return replay(existing)
        raise HTTPException(409, 'Не удалось сохранить. Повторите попытку.') from None
    return item


@router.get('')
def books(q: str = Query(default='', max_length=100), deleted: bool = False, status: Status | None = None,
          limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filters = [ReadingBook.user_id == user.id, ReadingBook.deleted_at.is_not(None) if deleted else ReadingBook.deleted_at.is_(None)]
    if status:
        filters.append(ReadingBook.status == status)
    items = db.scalars(select(ReadingBook).where(*filters).order_by(ReadingBook.created_at.desc(), ReadingBook.id)).all()
    if q.strip():
        items = [item for item in items if q.strip().casefold() in (item.title+' '+item.author).casefold()]
    return {'items': [serialize_book(db, item) for item in items[offset:offset+limit]], 'total': len(items), 'limit': limit, 'offset': offset}


@router.get('/reader-state/{content_id}')
def get_reader_state(content_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    checksum = book_checksum(content_id)
    item = db.scalar(select(ReaderState).where(ReaderState.user_id == user.id, ReaderState.content_id == content_id))
    if item and item.checksum == checksum:
        return {'location': item.location, 'bookmarks': item.bookmarks, 'checksum': checksum}
    return {'location': None, 'bookmarks': [], 'checksum': checksum}


@router.put('/reader-state/{content_id}')
def save_reader_state(content_id: str, payload: ReaderStateValues, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    checksum = book_checksum(content_id)
    length = len(book_paragraphs(content_id))
    if any(value.format != 'epub' for value in ([payload.location] if payload.location else []) + payload.bookmarks):
        raise HTTPException(422, 'Неверный формат закладки')
    positions = [value.position for value in ([payload.location] if payload.location else []) + payload.bookmarks]
    if any(value >= length for value in positions):
        raise HTTPException(422, 'Место чтения вне книги')
    item = db.scalar(select(ReaderState).where(ReaderState.user_id == context.user.id, ReaderState.content_id == content_id))
    if item is None:
        item = ReaderState(user_id=context.user.id, content_id=content_id, checksum=checksum)
        db.add(item)
    item.checksum = checksum
    item.location = payload.location.model_dump() if payload.location else None
    item.bookmarks = [value.model_dump() for value in payload.bookmarks]
    item.updated_at = utc_now()
    db.commit()
    return {'location': item.location, 'bookmarks': item.bookmarks, 'checksum': checksum}


@router.get('/{book_id}')
def get_book(book_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_book(db, owned(db, user.id, book_id))


@router.post('', status_code=201)
def create_book(payload: BookCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={'create_key', 'current_page'})
    data['initial_page'] = payload.current_page
    return serialize_book(db, create_once(db, ReadingBook, {'user_id': context.user.id}, payload.create_key, data))


@router.patch('/{book_id}')
def update_book(book_id: str, payload: BookValues, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, book_id)
    if item.deleted_at:
        raise HTTPException(409, 'Сначала восстановите книгу')
    max_page = db.scalar(select(func.max(ReadingLog.page)).where(ReadingLog.book_id == book_id, ReadingLog.deleted_at.is_(None))) or 0
    if payload.pages < max(item.initial_page, max_page):
        raise HTTPException(422, 'Число страниц меньше сохранённого прогресса')
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return serialize_book(db, item)


@router.delete('/{book_id}', status_code=204)
def delete_book(book_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, book_id)
    item.deleted_at = item.deleted_at or utc_now()
    db.commit()


@router.post('/{book_id}/restore')
def restore_book(book_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, book_id)
    item.deleted_at = None
    db.commit()
    return serialize_book(db, item)


@router.get('/{book_id}/logs')
def logs(book_id: str, q: str = Query(default='', max_length=100), deleted: bool = False,
         limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, user.id, book_id)
    filters = [ReadingLog.book_id == book_id, ReadingLog.deleted_at.is_not(None) if deleted else ReadingLog.deleted_at.is_(None)]
    if q.strip():
        filters.append(ReadingLog.search_text.contains(q.strip().casefold(), autoescape=True))
    items = db.scalars(select(ReadingLog).where(*filters).order_by(ReadingLog.date.desc(), ReadingLog.created_at.desc(), ReadingLog.id).offset(offset).limit(limit)).all()
    return {'items': [serialize_log(item) for item in items], 'total': db.scalar(select(func.count()).select_from(ReadingLog).where(*filters)), 'limit': limit, 'offset': offset}


def log_data(payload, book, user):
    if book.deleted_at:
        raise HTTPException(409, 'Сначала восстановите книгу')
    if payload.page is not None and not book.pages:
        raise HTTPException(422, 'Сначала укажите число страниц книги')
    if payload.page is not None and payload.page > book.pages:
        raise HTTPException(422, 'Страница больше числа страниц книги')
    if payload.date > local_date(user.timezone):
        raise HTTPException(422, 'Укажите дату уже состоявшегося чтения')
    data = payload.model_dump(exclude={'create_key'})
    data['search_text'] = '\n'.join([payload.chapter, payload.text, *payload.reflection.values()]).casefold()
    return data


@router.post('/{book_id}/logs', status_code=201)
def create_log(book_id: str, payload: LogCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    book = owned(db, context.user.id, book_id)
    return serialize_log(create_once(db, ReadingLog, {'book_id': book_id}, payload.create_key, log_data(payload, book, context.user)))


@router.patch('/{book_id}/logs/{log_id}')
def update_log(book_id: str, log_id: str, payload: LogValues, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    book = owned(db, context.user.id, book_id)
    item = owned_log(db, book_id, log_id)
    if item.deleted_at:
        raise HTTPException(409, 'Сначала восстановите запись')
    for key, value in log_data(payload, book, context.user).items():
        setattr(item, key, value)
    db.commit()
    return serialize_log(item)


@router.delete('/{book_id}/logs/{log_id}', status_code=204)
def delete_log(book_id: str, log_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    owned(db, context.user.id, book_id)
    item = owned_log(db, book_id, log_id)
    item.deleted_at = item.deleted_at or utc_now()
    db.commit()


@router.post('/{book_id}/logs/{log_id}/restore')
def restore_log(book_id: str, log_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    book = owned(db, context.user.id, book_id)
    item = owned_log(db, book_id, log_id)
    log_data(LogValues(**serialize_log(item)), book, context.user)
    item.deleted_at = None
    db.commit()
    return serialize_log(item)
