from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db, utc_now
from app.models import LoginSession, User


ACCESS_MINUTES = 15
REFRESH_DAYS = 30
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: LoginSession


def password_hash(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def password_matches(stored: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(stored, password)
    except VerificationError:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_for_session(session_id: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), f"csrf:{session_id}".encode("utf-8"), hashlib.sha256).hexdigest()


def new_refresh(session_id: str) -> str:
    return f"{session_id}.{secrets.token_urlsafe(48)}"


def access_jwt(user_id: str, session_id: str, secret: str) -> str:
    now = utc_now()
    return jwt.encode(
        {"sub": user_id, "sid": session_id, "iat": now, "exp": now + timedelta(minutes=ACCESS_MINUTES)},
        secret,
        algorithm="HS256",
    )


def start_session(db: Session, user: User, settings: Settings) -> tuple[LoginSession, str, str]:
    session = LoginSession(user_id=user.id, refresh_hash="", expires_at=utc_now() + timedelta(days=REFRESH_DAYS))
    db.add(session)
    db.flush()
    refresh = new_refresh(session.id)
    session.refresh_hash = token_hash(refresh)
    db.commit()
    return session, access_jwt(user.id, session.id, settings.jwt_secret), refresh


def set_auth_cookies(response: Response, settings: Settings, access: str, refresh: str) -> None:
    common = {"httponly": True, "secure": settings.secure_cookies, "samesite": "lax", "path": "/"}
    response.set_cookie(settings.access_cookie, access, max_age=ACCESS_MINUTES * 60, **common)
    response.set_cookie(settings.refresh_cookie, refresh, max_age=REFRESH_DAYS * 86400, **common)


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.access_cookie, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    response.delete_cookie(settings.refresh_cookie, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    settings: Settings = request.app.state.settings
    encoded = request.cookies.get(settings.access_cookie)
    if not encoded:
        raise HTTPException(status_code=401, detail="Требуется вход в аккаунт")
    try:
        claims = jwt.decode(encoded, settings.jwt_secret, algorithms=["HS256"])
        user_id = claims["sub"]
        session_id = claims["sid"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(status_code=401, detail="Сессия недействительна") from None
    login_session = db.get(LoginSession, session_id)
    if (
        login_session is None
        or login_session.user_id != user_id
        or login_session.revoked_at is not None
        or login_session.expires_at <= utc_now()
    ):
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    user = db.get(User, user_id)
    if user is None or user.verified_at is None:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    return AuthContext(user=user, session=login_session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def require_csrf(request: Request, context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)) -> AuthContext:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = csrf_for_session(context.session.id, request.app.state.settings.jwt_secret)
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Обновите страницу и повторите действие")
    # Every personal write uses this dependency. On PostgreSQL this row lock
    # serializes writes and archive snapshots for one account until commit.
    db.execute(select(User).where(User.id == context.user.id).with_for_update()).scalar_one()
    db.refresh(context.user)
    return context
