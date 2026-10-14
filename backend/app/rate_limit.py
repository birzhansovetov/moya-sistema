"""Database-backed limits for unauthenticated entry points."""

from datetime import timedelta
from hashlib import sha256

from fastapi import HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import utc_now
from app.models import AuthRateEvent


def _key(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _source(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(db: Session, request: Request, action: str, email: str, *, account_limit: int, source_limit: int, minutes: int) -> None:
    cutoff = utc_now() - timedelta(minutes=minutes)
    for scope, value, limit in (("account", email, account_limit), ("source", _source(request), source_limit)):
        count = db.scalar(select(func.count()).select_from(AuthRateEvent).where(
            AuthRateEvent.action == f"{action}_{scope}",
            AuthRateEvent.key_hash == _key(value),
            AuthRateEvent.created_at >= cutoff,
        ))
        if count is not None and count >= limit:
            raise HTTPException(status_code=429, detail="Слишком много попыток. Повторите позже", headers={"Retry-After": str(minutes * 60)})


def record(db: Session, request: Request, action: str, email: str) -> None:
    for scope, value in (("account", email), ("source", _source(request))):
        db.add(AuthRateEvent(action=f"{action}_{scope}", key_hash=_key(value)))
    db.execute(delete(AuthRateEvent).where(AuthRateEvent.created_at < utc_now() - timedelta(days=1)))
    db.commit()
