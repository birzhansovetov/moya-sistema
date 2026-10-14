"""Operator-only command for catalog revocation; never exposed as an HTTP route."""

import argparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import sqlalchemy_url, utc_now
from app.models import ContentRevocation, ContentRevocationEvent


def change_revocation(db: Session, action: str, kind: str, item_id: str, version: str, reason: str, actor: str) -> None:
    if action not in {"revoke", "restore"} or kind not in {"sport", "recipe", "study", "book", "guide"}:
        raise ValueError("Unknown action or content kind")
    if not all(value.strip() for value in (item_id, version, reason, actor)):
        raise ValueError("ID, version, reason and actor are required")
    row = db.scalar(select(ContentRevocation).where(ContentRevocation.kind == kind, ContentRevocation.item_id == item_id,
                                                     ContentRevocation.version == version))
    if row is None:
        if action == "restore":
            raise ValueError("Material has no revocation to restore")
        row = ContentRevocation(kind=kind, item_id=item_id, version=version, active=True, reason=reason.strip())
        db.add(row)
    else:
        if row.active == (action == "revoke"):
            raise ValueError("Material already has this state")
        row.active = action == "revoke"
        row.reason = reason.strip()
        row.updated_at = utc_now()
    db.add(ContentRevocationEvent(kind=kind, item_id=item_id, version=version, action=action,
                                  actor=actor.strip(), reason=reason.strip()))
    db.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a catalog revocation or restoration")
    parser.add_argument("action", choices=("revoke", "restore"))
    for option in ("kind", "id", "version", "reason", "actor"):
        parser.add_argument(f"--{option}", required=True)
    args = parser.parse_args()
    engine = create_engine(sqlalchemy_url(Settings.from_env().database_url))
    with Session(engine) as db:
        change_revocation(db, args.action, args.kind, args.id, args.version, args.reason, args.actor)
        db.commit()


if __name__ == "__main__":
    main()
