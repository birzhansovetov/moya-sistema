"""Versioned, encrypted snapshot of one account's personal records."""

from datetime import date, datetime
import json
import os
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Session

from app.db import utc_now
from app.models import (
    Expense, ExpenseCategory, Income, FoodLog, NutritionMenu, NutritionProfile,
    PersonalEntry, ReadingBook, ReadingLog, ReaderState, SportPlan, StudyAttempt,
    StudyDraft, StudyPlan, StudyReview, Subtask, Task, TaskCompletion,
    TrainingFeedback, User, WeightLog, WorkoutDraft, WorkoutLog,
)


MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAGIC = b"MOYABK"
FORMAT_VERSION = 1
HEADER_SIZE = len(MAGIC) + 1 + 16 + 12

PERSONAL_MODELS = (
    Task, Subtask, TaskCompletion,
    SportPlan, WorkoutLog, WorkoutDraft, TrainingFeedback,
    NutritionProfile, NutritionMenu, FoodLog, WeightLog,
    ExpenseCategory, Expense, Income,
    PersonalEntry, ReadingBook, ReadingLog, ReaderState,
    StudyPlan, StudyAttempt, StudyDraft, StudyReview,
)
PERSONAL_TABLES = {model.__tablename__: model for model in PERSONAL_MODELS}
LEGACY_PROFILE_FIELDS = {"name", "timezone", "hidden_sections", "hidden_spheres", "finance_currency"}
PREVIOUS_PROFILE_FIELDS = LEGACY_PROFILE_FIELDS | {"onboarding_answers", "onboarding_completed_at"}
PROFILE_FIELDS = PREVIOUS_PROFILE_FIELDS | {"onboarding_version"}
SECTIONS = {"personal", "sport", "nutrition", "education", "work", "finance", "other"}
SPHERES = {"health", "education", "profession", "languages", "finance", "personal"}
FINANCE_CURRENCIES = {"KZT", "USD", "EUR", "RUB", "GBP"}
SNAPSHOT_FIELDS = {"schema_version", "created_at", "email", "source_user_id", "profile", "tables"}
JSON_SHAPES = {
    "personal_entries": {"activities": (list,)},
    "tasks": {"weekdays": (list, type(None))},
    "sport_plans": {"answers": (dict,), "program_snapshot": (dict,)},
    "workout_logs": {"results": (list,)},
    "workout_drafts": {"actual": (dict,)},
    "nutrition_profiles": {"answers": (dict,), "preferences": (dict,), "estimate_snapshot": (dict,)},
    "nutrition_menus": {"days_snapshot": (list,), "profile_snapshot": (dict,)},
    "food_logs": {"recipe_snapshot": (dict,), "nutrition_snapshot": (dict,)},
    "reading_logs": {"reflection": (dict,)},
    "reader_states": {"location": (dict, type(None)), "bookmarks": (list,)},
    "study_plans": {"config": (dict,), "lesson_ids": (list,)},
    "study_attempts": {"snapshot": (dict,), "result": (dict,)},
    "study_drafts": {"content": (dict,)},
}


class ArchiveError(ValueError):
    """An archive cannot safely be opened or restored."""


def canonical_bytes(value: dict[str, Any]) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArchiveError("Неверная структура архива") from exc


def _derive_key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or not password:
        raise ArchiveError("Неверный пароль или повреждённый архив")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def seal_snapshot(snapshot: dict[str, Any], password: str) -> bytes:
    plaintext = canonical_bytes(snapshot)
    if len(plaintext) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Архив превышает допустимый размер")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + bytes([FORMAT_VERSION]) + salt + nonce
    encrypted = AESGCM(_derive_key(password, salt)).encrypt(nonce, plaintext, header)
    result = header + encrypted
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Архив превышает допустимый размер")
    return result


def _reject_constant(_value: str):
    raise ValueError("non-finite JSON value")


def open_snapshot(archive: bytes, password: str) -> dict[str, Any]:
    if not isinstance(archive, bytes) or len(archive) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Архив превышает допустимый размер")
    if len(archive) < HEADER_SIZE + 16 or archive[:len(MAGIC)] != MAGIC:
        raise ArchiveError("Неверный формат архива")
    if archive[len(MAGIC)] != FORMAT_VERSION:
        raise ArchiveError("Версия архива не поддерживается")
    header, encrypted = archive[:HEADER_SIZE], archive[HEADER_SIZE:]
    salt = header[len(MAGIC) + 1:len(MAGIC) + 17]
    nonce = header[-12:]
    try:
        plaintext = AESGCM(_derive_key(password, salt)).decrypt(nonce, encrypted, header)
    except (InvalidTag, ValueError) as exc:
        raise ArchiveError("Неверный пароль или повреждённый архив") from exc
    if len(plaintext) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Архив превышает допустимый размер")
    try:
        value = json.loads(plaintext, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ArchiveError("Неверная структура архива") from exc
    if not isinstance(value, dict):
        raise ArchiveError("Неверная структура архива")
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def snapshot_user(db: Session, user: User) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for model in PERSONAL_MODELS:
        if model in (Subtask, TaskCompletion):
            query = select(model).join(Task, model.task_id == Task.id).where(Task.user_id == user.id)
        elif model is ReadingLog:
            query = select(ReadingLog).join(ReadingBook, ReadingLog.book_id == ReadingBook.id).where(ReadingBook.user_id == user.id)
        else:
            query = select(model).where(model.user_id == user.id)
        rows = db.scalars(query).all()
        rows.sort(key=lambda row: row.id if hasattr(row, "id") else row.user_id)
        tables[model.__tablename__] = [
            {column.name: _plain(getattr(row, column.name)) for column in model.__table__.columns}
            for row in rows
        ]
    return {
        "schema_version": FORMAT_VERSION,
        "created_at": utc_now().isoformat() + "Z",
        "email": user.email,
        "source_user_id": user.id,
        "profile": {name: _plain(getattr(user, name)) for name in PROFILE_FIELDS},
        "tables": tables,
    }


def _valid_column_value(table: str, column, value: Any) -> bool:
    if value is None:
        return column.nullable
    kind = column.type
    if isinstance(kind, DateTime):
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False
    if isinstance(kind, Date):
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
    if isinstance(kind, Boolean):
        return isinstance(value, bool)
    if isinstance(kind, Integer):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(kind, String):
        return isinstance(value, str) and (kind.length is None or len(value) <= kind.length)
    if isinstance(kind, JSON):
        expected = JSON_SHAPES.get(table, {}).get(column.name)
        return expected is None or isinstance(value, expected)
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_snapshot(value: object, email: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SNAPSHOT_FIELDS or value["schema_version"] != FORMAT_VERSION:
        raise ArchiveError("Неверная структура архива")
    if not isinstance(value["email"], str) or value["email"].strip().casefold() != email.strip().casefold():
        raise ArchiveError("Архив принадлежит другому аккаунту")
    owner = value["source_user_id"]
    if not isinstance(owner, str) or not owner:
        raise ArchiveError("Неверная структура архива")
    try:
        datetime.fromisoformat(value["created_at"])
    except (TypeError, ValueError) as exc:
        raise ArchiveError("Неверная структура архива") from exc
    profile, tables = value["profile"], value["tables"]
    if not isinstance(profile, dict) or set(profile) not in (PROFILE_FIELDS, PREVIOUS_PROFILE_FIELDS, LEGACY_PROFILE_FIELDS) or not isinstance(tables, dict):
        raise ArchiveError("Неверная структура архива")
    current_tables = set(PERSONAL_TABLES)
    missing_tables = current_tables - set(tables)
    if set(tables) - current_tables or not missing_tables <= {"training_feedback", "workout_drafts", "incomes", "reader_states"}:
        raise ArchiveError("Неверная структура архива")
    for table in missing_tables:
        tables[table] = []
    if "onboarding_answers" in profile:
        from app.routes.onboarding import Survey
        from pydantic import ValidationError
        try:
            if profile["onboarding_answers"] is not None:
                Survey.model_validate(profile["onboarding_answers"])
            if profile["onboarding_completed_at"] is not None:
                datetime.fromisoformat(profile["onboarding_completed_at"])
            if "onboarding_version" in profile and profile["onboarding_version"] is not None and profile["onboarding_version"] != 1:
                raise ValueError("Неподдерживаемая версия анкеты")
        except (ValidationError, TypeError, ValueError) as exc:
            raise ArchiveError("Неверная анкета в архиве") from exc
    if profile["name"] is not None and (not isinstance(profile["name"], str) or len(profile["name"]) > 80):
        raise ArchiveError("Неверная структура архива")
    if not isinstance(profile["timezone"], str) or len(profile["timezone"]) > 64:
        raise ArchiveError("Неверная структура архива")
    try:
        ZoneInfo(profile["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise ArchiveError("Неверная структура архива") from exc
    if profile["finance_currency"] not in FINANCE_CURRENCIES:
        raise ArchiveError("Неверная структура архива")
    if any(not isinstance(profile[key], list) or any(not isinstance(item, str) for item in profile[key]) for key in ("hidden_sections", "hidden_spheres")):
        raise ArchiveError("Неверная структура архива")
    if (len(profile["hidden_sections"]) != len(set(profile["hidden_sections"])) or not set(profile["hidden_sections"]) <= SECTIONS
            or len(profile["hidden_spheres"]) != len(set(profile["hidden_spheres"])) or not set(profile["hidden_spheres"]) <= SPHERES):
        raise ArchiveError("Неверная структура архива")
    ids: dict[str, set[str]] = {}
    for table, model in PERSONAL_TABLES.items():
        rows = tables[table]
        if not isinstance(rows, list):
            raise ArchiveError("Неверная структура архива")
        expected = {column.name for column in model.__table__.columns}
        identity = "user_id" if model is NutritionProfile else "id"
        seen: set[str] = set()
        for row in rows:
            if table == "personal_entries" and isinstance(row, dict) and "activities" not in row:
                row["activities"] = [row["activity"]] if row.get("activity") not in (None, "other") else []
            if not isinstance(row, dict) or set(row) != expected:
                raise ArchiveError("Неверная структура архива")
            if any(not _valid_column_value(table, column, row[column.name]) for column in model.__table__.columns):
                raise ArchiveError("Неверная структура архива")
            if "user_id" in row and row["user_id"] != owner:
                raise ArchiveError("Неверная структура архива")
            key = row[identity]
            if not isinstance(key, str) or not key or key in seen:
                raise ArchiveError("Неверная структура архива")
            seen.add(key)
        ids[table] = seen
        for constraint in model.__table__.constraints:
            if not isinstance(constraint, UniqueConstraint):
                continue
            keys: set[tuple] = set()
            for row in rows:
                unique_key = tuple(row[column.name] for column in constraint.columns)
                if any(item is None for item in unique_key):
                    continue
                if unique_key in keys:
                    raise ArchiveError("Неверная структура архива")
                keys.add(unique_key)
    for table, model in PERSONAL_TABLES.items():
        for row in tables[table]:
            for column in model.__table__.columns:
                for foreign_key in column.foreign_keys:
                    target = foreign_key.column.table.name
                    if target == "users":
                        continue
                    if row[column.name] not in ids[target]:
                        raise ArchiveError("Неверная связь в архиве")
    canonical_bytes(value)
    return value
