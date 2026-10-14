"""Manual encrypted export and guarded replacement of one user's records."""

from datetime import date, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
import jwt
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, password_matches, require_csrf
from app.backup_archive import (
    ArchiveError, MAX_ARCHIVE_BYTES, PERSONAL_MODELS, canonical_bytes,
    open_snapshot, seal_snapshot, snapshot_user, validate_snapshot,
)
from app.db import get_db, utc_now
from app.models import BackupUse, ReadingBook, ReadingLog, Subtask, Task, TaskCompletion


router = APIRouter(prefix="/api/profile/backup", tags=["backup"])
TOKEN_MINUTES = 10


class ExportRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)


class SafetyCopyRequest(ExportRequest):
    preview_token: str = Field(min_length=1)


def _check_current_password(context: AuthContext, password: str) -> None:
    if not password_matches(context.user.password_hash, password):
        raise HTTPException(status_code=403, detail="Неверный текущий пароль")


def _file_response(archive: bytes, restore_token: str | None = None) -> Response:
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="personal.moya-backup"',
        "X-Content-Type-Options": "nosniff",
    }
    if restore_token:
        headers["X-Restore-Token"] = restore_token
    return Response(content=archive, media_type="application/octet-stream", headers=headers)


def _state_digest(snapshot: dict[str, Any]) -> str:
    stable = {key: value for key, value in snapshot.items() if key != "created_at"}
    return sha256(canonical_bytes(stable)).hexdigest()


def _token(context: AuthContext, kind: str, data: dict[str, str], secret: str) -> str:
    return jwt.encode({
        "kind": kind, "sub": context.user.id, "sid": context.session.id,
        "exp": utc_now() + timedelta(minutes=TOKEN_MINUTES), **data,
    }, secret, algorithm="HS256")


def _claims(context: AuthContext, token: str, kind: str, secret: str) -> dict:
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=409, detail="Проверка архива устарела. Начните заново") from None
    if (claims.get("kind") != kind or claims.get("sub") != context.user.id
            or claims.get("sid") != context.session.id
            or not isinstance(claims.get("file_sha"), str)
            or not isinstance(claims.get("state_sha"), str)):
        raise HTTPException(status_code=409, detail="Проверка архива устарела. Начните заново")
    if kind == "restore" and not isinstance(claims.get("jti"), str):
        raise HTTPException(status_code=409, detail="Проверка архива устарела. Начните заново")
    return claims


async def _read_archive(upload: UploadFile) -> bytes:
    try:
        archive = await upload.read(MAX_ARCHIVE_BYTES + 1)
    finally:
        await upload.close()
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="Архив слишком большой")
    return archive


def _checked_archive(archive: bytes, password: str, email: str) -> dict:
    try:
        return validate_snapshot(open_snapshot(archive, password), email)
    except ArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/export")
def export(payload: ExportRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    _check_current_password(context, payload.current_password)
    try:
        archive = seal_snapshot(snapshot_user(db, context.user), payload.current_password)
    except ArchiveError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from None
    return _file_response(archive)


@router.post("/preview")
async def preview(
    request: Request,
    archive: UploadFile = File(...), archive_password: str = Form(...),
    context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db),
):
    content = await _read_archive(archive)
    saved = _checked_archive(content, archive_password, context.user.email)
    current = snapshot_user(db, context.user)
    return {
        "created_at": saved["created_at"],
        "counts": {name: len(rows) for name, rows in saved["tables"].items()},
        "preview_token": _token(context, "preview", {"file_sha": sha256(content).hexdigest(), "state_sha": _state_digest(current)}, request.app.state.settings.jwt_secret),
    }


@router.post("/safety-copy")
def safety_copy(payload: SafetyCopyRequest, request: Request, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    _check_current_password(context, payload.current_password)
    claims = _claims(context, payload.preview_token, "preview", request.app.state.settings.jwt_secret)
    snapshot = snapshot_user(db, context.user)
    if _state_digest(snapshot) != claims["state_sha"]:
        raise HTTPException(status_code=409, detail="Данные изменились. Проверьте архив заново")
    try:
        encrypted = seal_snapshot(snapshot, payload.current_password)
    except ArchiveError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from None
    token = _token(context, "restore", {
        "file_sha": claims["file_sha"], "state_sha": claims["state_sha"], "jti": str(uuid4()),
    }, request.app.state.settings.jwt_secret)
    return _file_response(encrypted, token)


def _row_from_archive(model, row: dict[str, Any], current_user_id: str) -> dict[str, Any]:
    converted = row.copy()
    for column in model.__table__.columns:
        name = column.name
        if name == "user_id":
            converted[name] = current_user_id
        elif converted[name] is not None and isinstance(column.type, DateTime):
            converted[name] = datetime.fromisoformat(converted[name])
        elif converted[name] is not None and isinstance(column.type, Date):
            converted[name] = date.fromisoformat(converted[name])
    return converted


def _replace_personal(db: Session, user_id: str, saved: dict[str, Any]) -> None:
    for model in reversed(PERSONAL_MODELS):
        if model in (Subtask, TaskCompletion):
            ids = select(Task.id).where(Task.user_id == user_id)
            predicate = model.task_id.in_(ids)
        elif model is ReadingLog:
            ids = select(ReadingBook.id).where(ReadingBook.user_id == user_id)
            predicate = ReadingLog.book_id.in_(ids)
        else:
            predicate = model.user_id == user_id
        db.execute(delete(model).where(predicate))
    db.flush()
    for model in PERSONAL_MODELS:
        rows = saved["tables"][model.__tablename__]
        db.add_all(model(**_row_from_archive(model, row, user_id)) for row in rows)
        db.flush()


@router.post("/restore")
async def restore(
    request: Request,
    archive: UploadFile = File(...), archive_password: str = Form(...),
    current_password: str = Form(...), restore_token: str = Form(...),
    context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db),
):
    _check_current_password(context, current_password)
    claims = _claims(context, restore_token, "restore", request.app.state.settings.jwt_secret)
    content = await _read_archive(archive)
    if sha256(content).hexdigest() != claims["file_sha"]:
        raise HTTPException(status_code=409, detail="Выбран другой архив. Начните проверку заново")
    saved = _checked_archive(content, archive_password, context.user.email)
    if db.get(BackupUse, claims["jti"]) is not None:
        raise HTTPException(status_code=409, detail="Этот архив уже восстановлен")
    if _state_digest(snapshot_user(db, context.user)) != claims["state_sha"]:
        raise HTTPException(status_code=409, detail="Данные изменились. Проверьте архив заново")
    try:
        _replace_personal(db, context.user.id, saved)
        for key, value in saved["profile"].items():
            if key == "onboarding_completed_at" and value is not None:
                value = datetime.fromisoformat(value)
            setattr(context.user, key, value)
        if "onboarding_version" not in saved["profile"]:
            context.user.onboarding_version = 1 if saved["profile"].get("onboarding_answers") is not None else None
        db.add(BackupUse(id=claims["jti"], user_id=context.user.id))
        db.commit()
    except (IntegrityError, ValueError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="Архив не удалось восстановить. Данные не изменены") from None
    return {"status": "restored", "counts": {name: len(rows) for name, rows in saved["tables"].items()}}
