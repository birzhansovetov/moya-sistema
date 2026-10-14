from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    """Store all instants as naive UTC; user-facing dates stay local calendar dates."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sqlalchemy_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def get_db(request: Request):
    with request.app.state.sessionmaker() as db:
        yield db
