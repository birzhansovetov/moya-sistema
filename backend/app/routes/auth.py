from datetime import timedelta
import hmac
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    access_jwt,
    clear_auth_cookies,
    csrf_for_session,
    get_auth_context,
    new_refresh,
    password_hash,
    password_matches,
    require_csrf,
    set_auth_cookies,
    start_session,
    token_hash,
)
from app.config import Settings
from app.db import get_db, utc_now
from app.models import EmailToken, LoginSession, User
from app.rate_limit import enforce, record


router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class EmailOnly(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class TokenOnly(BaseModel):
    token: str = Field(min_length=16)


class VerifyConfirm(TokenOnly):
    password: str = Field(min_length=12, max_length=256)


class ResetConfirm(BaseModel):
    token: str = Field(min_length=16)
    password: str = Field(min_length=12, max_length=256)


def normalized_email(email: str) -> str:
    return email.strip().casefold()


def create_email_token(db: Session, user: User, kind: str, minutes: int) -> str:
    token = secrets.token_urlsafe(40)
    db.add(
        EmailToken(
            user_id=user.id,
            kind=kind,
            token_hash=token_hash(token),
            expires_at=utc_now() + timedelta(minutes=minutes),
        )
    )
    db.commit()
    return token


def get_valid_email_token(db: Session, value: str, kind: str) -> EmailToken:
    entry = db.scalar(
        select(EmailToken).where(EmailToken.token_hash == token_hash(value), EmailToken.kind == kind)
    )
    if entry is None or entry.used_at is not None or entry.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="Ссылка недействительна или срок её действия истёк")
    return entry


def send_action_mail(request: Request, user: User, token: str, kind: str) -> None:
    settings: Settings = request.app.state.settings
    if kind == "verify":
        path = "/verify-email"
        subject = "Подтверждение адреса — Моя система"
        intro = "Подтвердите адрес электронной почты:"
    else:
        path = "/reset-password"
        subject = "Сброс пароля — Моя система"
        intro = "Чтобы задать новый пароль, откройте ссылку:"
    # Fragment values never reach the web server in the browser's HTTP request.
    link = f"{settings.frontend_origin}{path}#token={quote(token)}"
    try:
        request.app.state.mailer.send(user.email, subject, f"{intro}\n{link}\nЕсли запрос был не от вас, проигнорируйте письмо.")
    except Exception:
        raise HTTPException(status_code=503, detail="Письмо не отправлено. Повторите попытку позже") from None


def send_with_token_cleanup(request: Request, db: Session, user: User, token: str, kind: str) -> None:
    try:
        send_action_mail(request, user, token, kind)
    except HTTPException:
        entry = db.scalar(select(EmailToken).where(EmailToken.token_hash == token_hash(token)))
        if entry is not None:
            db.delete(entry)
            db.commit()
        raise


def sent_recently(db: Session, user: User, kind: str, lifetime_minutes: int) -> bool:
    latest = db.scalar(
        select(EmailToken).where(EmailToken.user_id == user.id, EmailToken.kind == kind, EmailToken.used_at.is_(None))
        .order_by(EmailToken.expires_at.desc()).limit(1)
    )
    return latest is not None and latest.expires_at > utc_now() + timedelta(minutes=lifetime_minutes - 5)


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register(payload: EmailOnly, request: Request, db: Session = Depends(get_db)):
    email = normalized_email(str(payload.email))
    enforce(db, request, "register", email, account_limit=5, source_limit=30, minutes=60)
    record(db, request, "register", email)
    existing = db.scalar(select(User).where(User.email == email))
    if existing is None:
        # Only the holder of the emailed token may choose the first usable password.
        user = User(email=email, password_hash=password_hash(secrets.token_urlsafe(40)))
        db.add(user)
        db.commit()
        db.refresh(user)
    elif existing.verified_at is None:
        user = existing
        if sent_recently(db, user, "verify", 24 * 60):
            return {"message": "Если адрес доступен, проверьте почту для подтверждения"}
    else:
        return {"message": "Если адрес доступен, проверьте почту для подтверждения"}
    token = create_email_token(db, user, "verify", 24 * 60)
    send_with_token_cleanup(request, db, user, token, "verify")
    return {"message": "Если адрес доступен, проверьте почту для подтверждения"}


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(payload: VerifyConfirm, db: Session = Depends(get_db)):
    entry = get_valid_email_token(db, payload.token, "verify")
    user = db.get(User, entry.user_id)
    if user is None or user.verified_at is not None:
        raise HTTPException(status_code=400, detail="Ссылка недействительна")
    user.password_hash = password_hash(payload.password)
    user.verified_at = utc_now()
    entry.used_at = utc_now()
    db.commit()
    return Response(status_code=204)


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    settings: Settings = request.app.state.settings
    email = normalized_email(str(payload.email))
    enforce(db, request, "login", email, account_limit=10, source_limit=200, minutes=15)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not password_matches(user.password_hash, payload.password):
        record(db, request, "login", email)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if user.verified_at is None:
        raise HTTPException(status_code=403, detail="Подтвердите email перед входом")
    session, access, refresh = start_session(db, user, settings)
    set_auth_cookies(response, settings, access, refresh)
    return {"user": user_info(user), "csrf_token": csrf_for_session(session.id, settings.jwt_secret)}


def user_info(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "timezone": user.timezone,
            "onboarding_complete": user.onboarding_completed_at is not None}


@router.get("/me")
def me(request: Request, context: AuthContext = Depends(get_auth_context)):
    return {
        "user": user_info(context.user),
        "csrf_token": csrf_for_session(context.session.id, request.app.state.settings.jwt_secret),
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    settings: Settings = request.app.state.settings
    old_refresh = request.cookies.get(settings.refresh_cookie, "")
    session_id, separator, _ = old_refresh.partition(".")
    if not separator:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    login_session = db.get(LoginSession, session_id)
    if (
        login_session is None
        or login_session.revoked_at is not None
        or login_session.expires_at <= utc_now()
        or not hmac.compare_digest(login_session.refresh_hash, token_hash(old_refresh))
    ):
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    expected_csrf = csrf_for_session(session_id, settings.jwt_secret)
    user = db.get(User, login_session.user_id)
    if user is None or user.verified_at is None:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    new_value = new_refresh(session_id)
    login_session.refresh_hash = token_hash(new_value)
    db.commit()
    set_auth_cookies(response, settings, access_jwt(user.id, session_id, settings.jwt_secret), new_value)
    return {"user": user_info(user), "csrf_token": expected_csrf}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    context.session.revoked_at = utc_now()
    db.commit()
    clear_auth_cookies(response, request.app.state.settings)
    response.status_code = 204


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: EmailOnly, request: Request, db: Session = Depends(get_db)):
    email = normalized_email(str(payload.email))
    enforce(db, request, "reset", email, account_limit=5, source_limit=30, minutes=60)
    record(db, request, "reset", email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.verified_at is not None:
        if not sent_recently(db, user, "reset", 30):
            token = create_email_token(db, user, "reset", 30)
            send_with_token_cleanup(request, db, user, token, "reset")
    return {"message": "Если адрес зарегистрирован, отправлена ссылка для сброса"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: ResetConfirm, db: Session = Depends(get_db)):
    entry = get_valid_email_token(db, payload.token, "reset")
    user = db.get(User, entry.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Ссылка недействительна")
    user.password_hash = password_hash(payload.password)
    entry.used_at = utc_now()
    for session in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))):
        session.revoked_at = utc_now()
    db.commit()
    return Response(status_code=204)
