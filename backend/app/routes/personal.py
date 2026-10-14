import hashlib
import json
from datetime import date as DateValue
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db, utc_now
from app.models import PersonalEntry, User

router = APIRouter(prefix='/api/personal/entries', tags=['personal'])
Kind = Literal['diary', 'event', 'experiment']


class EntryValues(BaseModel):
    kind: Kind
    title: str = Field(default='', max_length=160)
    body: str = Field(default='', max_length=20000)
    date: DateValue | None = None
    mood: Literal['great', 'good', 'neutral', 'low', 'hard'] | None = None
    activity: Literal['meeting', 'hobby', 'travel', 'rest', 'other'] = 'other'
    completed: bool = False
    impression: str = Field(default='', max_length=10000)

    @model_validator(mode='after')
    def validate_entry(self):
        self.title, self.body, self.impression = self.title.strip(), self.body.strip(), self.impression.strip()
        if self.kind == 'diary':
            if self.date is None:
                raise ValueError('Укажите дату записи дневника')
            if not self.title and not self.body:
                raise ValueError('Добавьте текст или заголовок записи')
        elif not self.title:
            raise ValueError('Укажите название события или идеи')
        return self


class EntryCreate(EntryValues):
    create_key: str = Field(min_length=1, max_length=100)


def serialize(item):
    return {**{key: getattr(item, key) for key in EntryValues.model_fields}, 'id': item.id,
            'date': item.date.isoformat() if item.date else None, 'deleted': item.deleted_at is not None}


def owned(db, user_id, entry_id):
    item = db.get(PersonalEntry, entry_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(404, 'Запись не найдена')
    return item


def values(payload):
    result = payload.model_dump(exclude={'create_key'})
    result['search_text'] = '\n'.join([payload.title, payload.body, payload.impression]).casefold()
    return result


@router.get('')
def listing(kind: Kind | None = None, start: DateValue | None = None, end: DateValue | None = None,
            q: str = Query(default='', max_length=100), deleted: bool = False,
            limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if start and end and start > end:
        raise HTTPException(422, 'Начало периода позже окончания')
    filters = [PersonalEntry.user_id == user.id, PersonalEntry.deleted_at.is_not(None) if deleted else PersonalEntry.deleted_at.is_(None)]
    if kind:
        filters.append(PersonalEntry.kind == kind)
    if start:
        filters.append(PersonalEntry.date >= start)
    if end:
        filters.append(PersonalEntry.date <= end)
    if q.strip():
        filters.append(PersonalEntry.search_text.contains(q.strip().casefold(), autoescape=True))
    items = db.scalars(select(PersonalEntry).where(*filters).order_by(PersonalEntry.date.desc(), PersonalEntry.created_at.desc(), PersonalEntry.id).offset(offset).limit(limit)).all()
    return {'items': [serialize(item) for item in items], 'total': db.scalar(select(func.count()).select_from(PersonalEntry).where(*filters)), 'limit': limit, 'offset': offset}


@router.get('/{entry_id}')
def read(entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize(owned(db, user.id, entry_id))


@router.post('', status_code=201)
def create(payload: EntryCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    data = values(payload)
    fingerprint = hashlib.sha256(json.dumps(data, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def replay(item):
        if item.create_fingerprint != fingerprint:
            raise HTTPException(409, 'Этот ключ уже использован для другой записи')
        if item.deleted_at:
            raise HTTPException(409, 'Запись удалена. Восстановите её из удалённых.')
        return serialize(item)

    query = select(PersonalEntry).where(PersonalEntry.user_id == context.user.id, PersonalEntry.create_key == payload.create_key)
    existing = db.scalar(query)
    if existing:
        return replay(existing)
    item = PersonalEntry(user_id=context.user.id, create_key=payload.create_key, create_fingerprint=fingerprint, **data)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query)
        if existing:
            return replay(existing)
        raise HTTPException(409, 'Не удалось сохранить запись. Повторите попытку.') from None
    return serialize(item)


@router.patch('/{entry_id}')
def update(entry_id: str, payload: EntryValues, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, entry_id)
    if item.deleted_at:
        raise HTTPException(409, 'Сначала восстановите запись')
    for key, value in values(payload).items():
        setattr(item, key, value)
    db.commit()
    return serialize(item)


@router.delete('/{entry_id}', status_code=204)
def delete(entry_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, entry_id)
    item.deleted_at = item.deleted_at or utc_now()
    db.commit()


@router.post('/{entry_id}/restore')
def restore(entry_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = owned(db, context.user.id, entry_id)
    item.deleted_at = None
    db.commit()
    return serialize(item)
