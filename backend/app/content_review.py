"""Eligibility and stable fingerprints for authored catalog variants."""

import hashlib
import json
from datetime import date
from importlib.resources import files
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentRevocation


def load_reviews() -> dict[str, Any]:
    return json.loads(files("app.content").joinpath("content_review.json").read_text(encoding="utf-8"))


def reviewed_variant(kind: str, item: dict[str, Any], today: date) -> bool:
    review = item.get("review")
    if not isinstance(review, dict):
        return False
    if not all(isinstance(review.get(key), str) and review[key].strip() for key in ("license", "source", "checked_at", "checked_by", "recheck_by")):
        return False
    try:
        if not date.fromisoformat(review["checked_at"]) <= today <= date.fromisoformat(review["recheck_by"]):
            return False
    except ValueError:
        return False
    if kind == "recipe":
        return isinstance(item.get("allergens"), list) and review.get("allergens_checked") is True
    if kind == "sport":
        return isinstance(item.get("limitations_supported"), bool) and review.get("safety_checked") is True
    return True


def variant_digest(kind: str, item: dict[str, Any], dependencies: dict[str, Any]) -> str:
    payload = {"kind": kind, "item": item, "dependencies": dependencies}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def revocation_reason(db: Session, kind: str, item_id: str, version: str) -> str | None:
    row = db.scalar(select(ContentRevocation).where(ContentRevocation.kind == kind, ContentRevocation.item_id == item_id,
                                                     ContentRevocation.version == version, ContentRevocation.active.is_(True)))
    return row.reason if row else None


def is_revoked(db: Session, kind: str, item_id: str, version: str) -> bool:
    return revocation_reason(db, kind, item_id, version) is not None
