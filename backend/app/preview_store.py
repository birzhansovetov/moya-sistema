"""Server-owned 30-minute matching snapshots."""

import hashlib
import json
import secrets
import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utc_now
from app.models import MatchingPreview, SportPlan, StudyPlan, User


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def create_preview(db: Session, user: User, survey: dict, match: dict) -> tuple[str, MatchingPreview]:
    raw = secrets.token_urlsafe(32)
    active_sport = db.scalar(select(SportPlan.id).where(SportPlan.user_id == user.id, SportPlan.active_key == "active"))
    studies = db.scalars(select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.active_slot.is_not(None))).all()
    preview = MatchingPreview(user_id=user.id, nonce_hash=_digest(raw), survey_version=1, answers=survey,
        answers_digest=hashlib.sha256(json.dumps(survey,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest(),
        candidates=match["candidates_by_sphere"], areas=match["areas"],
        expected_active={"sport": active_sport, "study": {item.course_id: item.id for item in studies}},
        expires_at=utc_now() + timedelta(minutes=30))
    db.add(preview)
    db.flush()
    return raw, preview


def load_preview(db: Session, user_id: str, raw: str) -> MatchingPreview | None:
    row = load_preview_any(db, user_id, raw)
    return row if row and row.expires_at > utc_now() else None


def load_preview_any(db: Session, user_id: str, raw: str) -> MatchingPreview | None:
    if not isinstance(raw, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', raw):
        return None
    return db.scalar(select(MatchingPreview).where(MatchingPreview.user_id == user_id,
        MatchingPreview.nonce_hash == _digest(raw)))
