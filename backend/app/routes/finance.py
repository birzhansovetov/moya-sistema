import calendar
import hashlib
import json
from datetime import date as DateValue, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db, utc_now
from app.models import Expense, ExpenseCategory, User

router = APIRouter(prefix="/api/finance", tags=["finance"])
Currency = Literal["KZT", "USD", "EUR", "RUB", "GBP"]
DEFAULT_CATEGORIES = ["Продукты", "Кафе", "Транспорт", "Жильё", "Обучение", "Здоровье", "Развлечения", "Другое"]


class CurrencyRequest(BaseModel):
    currency: Currency


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Укажите название категории")
        return value


class ExpenseValues(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("9999999999.99"), max_digits=12, decimal_places=2, allow_inf_nan=False)
    currency: Currency
    category_id: str
    date: DateValue | None = None
    note: str = Field(default="", max_length=500)


class ExpenseCreate(ExpenseValues):
    create_key: str = Field(min_length=1, max_length=100)


def _today(user: User) -> DateValue:
    return datetime.now(ZoneInfo(user.timezone)).date()


def _money(value) -> str:
    return f"{Decimal(value or 0) / 100:.2f}"


def _category(category: ExpenseCategory) -> dict:
    return {"id": category.id, "name": category.name}


def _categories(db: Session, user_id: str):
    # Stable IDs make lazy creation of the eight defaults safe to retry.
    # GET /categories also creates defaults; coordinate it with archive restore.
    db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one()
    missing = []
    for index, name in enumerate(DEFAULT_CATEGORIES):
        category_id = str(uuid5(NAMESPACE_URL, f"moya-finance:{user_id}:{index}"))
        if db.get(ExpenseCategory, category_id) is None:
            missing.append(ExpenseCategory(id=category_id, user_id=user_id, name=name, name_key=name.casefold(), position=index))
    if missing:
        db.add_all(missing)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one()
            if any(db.get(ExpenseCategory, item.id) is None for item in missing):
                raise HTTPException(409, "Не удалось подготовить категории. Повторите попытку.") from None
    return db.scalars(select(ExpenseCategory).where(ExpenseCategory.user_id == user_id).order_by(ExpenseCategory.position, ExpenseCategory.name)).all()


def _owned_category(db, user_id, category_id):
    category = db.get(ExpenseCategory, category_id)
    if category is None or category.user_id != user_id:
        raise HTTPException(404, "Категория не найдена")
    return category


def _owned_expense(db, user_id, expense_id):
    item = db.get(Expense, expense_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(404, "Расход не найден")
    return item


def _expense(item, category):
    return {"id": item.id, "amount": _money(item.amount_minor), "currency": item.currency,
            "category_id": item.category_id, "category_name": category.name, "date": item.expense_date.isoformat(),
            "note": item.note, "deleted": item.deleted_at is not None}


def _values(payload, user):
    day = payload.date or _today(user)
    if day > _today(user):
        raise HTTPException(422, "Укажите дату уже совершённого расхода")
    return {"amount_minor": int(payload.amount * 100), "currency": payload.currency, "category_id": payload.category_id,
            "expense_date": day, "note": payload.note.strip(), "note_search": payload.note.strip().casefold()}


def _month(month: str):
    try:
        start = DateValue.fromisoformat(month + "-01")
        return start, start.replace(day=calendar.monthrange(start.year, start.month)[1])
    except ValueError:
        raise HTTPException(422, "Укажите месяц в формате ГГГГ-ММ") from None


@router.get("/settings")
def settings(user: User = Depends(get_current_user)):
    return {"currency": user.finance_currency, "currencies": ["KZT", "USD", "EUR", "RUB", "GBP"]}


@router.patch("/settings")
def set_settings(payload: CurrencyRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    context.user.finance_currency = payload.currency
    db.commit()
    return settings(context.user)


@router.get("/categories")
def categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = [_category(item) for item in _categories(db, user.id)]
    db.commit()
    return {"items": items}


@router.post("/categories", status_code=201)
def add_category(payload: CategoryRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    _categories(db, context.user.id)
    item = ExpenseCategory(user_id=context.user.id, name=payload.name, name_key=payload.name.casefold())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Категория с таким названием уже есть") from None
    return _category(item)


@router.patch("/categories/{category_id}")
def rename_category(category_id: str, payload: CategoryRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = _owned_category(db, context.user.id, category_id)
    item.name, item.name_key = payload.name, payload.name.casefold()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Категория с таким названием уже есть") from None
    return _category(item)


@router.get("/expenses")
def expenses(start: DateValue | None = None, end: DateValue | None = None, currency: Currency | None = None,
             category_id: str | None = None, q: str = Query(default="", max_length=100), deleted: bool = False,
             limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    default_start, default_end = _month(_today(user).strftime("%Y-%m"))
    start, end = start or default_start, end or default_end
    if start > end:
        raise HTTPException(422, "Начало периода позже его окончания")
    filters = [Expense.user_id == user.id, Expense.currency == (currency or user.finance_currency),
               Expense.expense_date >= start, Expense.expense_date <= end,
               Expense.deleted_at.is_not(None) if deleted else Expense.deleted_at.is_(None)]
    if category_id:
        filters.append(Expense.category_id == category_id)
    if q.strip():
        search = q.strip().casefold()
        filters.append(or_(Expense.note_search.contains(search, autoescape=True), ExpenseCategory.name_key.contains(search, autoescape=True)))
    query = select(Expense, ExpenseCategory).join(ExpenseCategory).where(*filters)
    count = db.scalar(select(func.count()).select_from(Expense).join(ExpenseCategory).where(*filters))
    rows = db.execute(query.order_by(Expense.expense_date.desc(), Expense.created_at.desc(), Expense.id).limit(limit).offset(offset)).all()
    return {"items": [_expense(item, category) for item, category in rows], "total": count, "limit": limit, "offset": offset}


@router.post("/expenses", status_code=201)
def add_expense(payload: ExpenseCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    values = _values(payload, context.user)
    category = _owned_category(db, context.user.id, payload.category_id)
    fingerprint = hashlib.sha256(json.dumps(values, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def replay(item):
        if item.create_fingerprint != fingerprint:
            raise HTTPException(409, "Этот ключ сохранения уже использован для другого расхода")
        if item.deleted_at is not None:
            raise HTTPException(409, "Расход уже удалён. Его можно восстановить в удалённых записях.")
        return _expense(item, _owned_category(db, context.user.id, item.category_id))

    existing = db.scalar(select(Expense).where(Expense.user_id == context.user.id, Expense.create_key == payload.create_key))
    if existing:
        return replay(existing)
    item = Expense(user_id=context.user.id, create_key=payload.create_key, create_fingerprint=fingerprint, **values)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Expense).where(Expense.user_id == context.user.id, Expense.create_key == payload.create_key))
        if existing:
            return replay(existing)
        raise HTTPException(409, "Не удалось сохранить расход. Повторите попытку.") from None
    return _expense(item, category)


@router.patch("/expenses/{expense_id}")
def edit_expense(expense_id: str, payload: ExpenseValues, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = _owned_expense(db, context.user.id, expense_id)
    if item.deleted_at is not None:
        raise HTTPException(409, "Сначала восстановите удалённый расход")
    category = _owned_category(db, context.user.id, payload.category_id)
    for key, value in _values(payload, context.user).items():
        setattr(item, key, value)
    db.commit()
    return _expense(item, category)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = _owned_expense(db, context.user.id, expense_id)
    item.deleted_at = item.deleted_at or utc_now()
    db.commit()


@router.post("/expenses/{expense_id}/restore")
def restore_expense(expense_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = _owned_expense(db, context.user.id, expense_id)
    item.deleted_at = None
    db.commit()
    return _expense(item, _owned_category(db, context.user.id, item.category_id))


@router.get("/summary")
def summary(month: str = Query(pattern=r"^\d{4}-\d{2}$"), currency: Currency | None = None,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    month_start, month_end = _month(month)
    today = _today(user)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    currency = currency or user.finance_currency
    scope = [Expense.user_id == user.id, Expense.currency == currency, Expense.deleted_at.is_(None)]
    today_sum, week_sum, month_sum = db.execute(select(
        func.sum(case((Expense.expense_date == today, Expense.amount_minor), else_=0)),
        func.sum(case((Expense.expense_date.between(week_start, week_end), Expense.amount_minor), else_=0)),
        func.sum(case((Expense.expense_date.between(month_start, month_end), Expense.amount_minor), else_=0)),
    ).where(*scope)).one()
    grouped = db.execute(select(ExpenseCategory.id, ExpenseCategory.name, func.sum(Expense.amount_minor).label("total"))
                         .join(Expense, Expense.category_id == ExpenseCategory.id)
                         .where(*scope, Expense.expense_date.between(month_start, month_end))
                         .group_by(ExpenseCategory.id, ExpenseCategory.name).order_by(func.sum(Expense.amount_minor).desc())).all()
    return {"currency": currency, "today": today.isoformat(), "week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
            "month": month, "today_total": _money(today_sum), "week_total": _money(week_sum), "month_total": _money(month_sum),
            "categories": [{"id": category_id, "name": name, "amount": _money(total)} for category_id, name, total in grouped]}
