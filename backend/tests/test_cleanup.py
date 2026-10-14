from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.cleanup import cleanup_onboarding
from app.db import Base, utc_now
from app.models import MatchingPreview, MatchingStartResult, User
from app.preview_store import create_preview


def test_cleanup_removes_expired_preview_and_old_result_without_user(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="cleanup@example.com", password_hash="x")
        db.add(user); db.flush()
        _, old = create_preview(db, user, {}, {"areas": {}, "candidates_by_sphere": {}})
        old.expires_at = utc_now() - timedelta(days=9)
        old.created_at = utc_now() - timedelta(days=9)
        db.add(MatchingStartResult(user_id=user.id, nonce_hash=old.nonce_hash, payload_digest="x", response={},
                                   created_at=utc_now() - timedelta(days=8)))
        db.commit()
        assert cleanup_onboarding(db) == (1, 1)
        db.commit()
        assert db.scalar(select(MatchingPreview)) is None
        assert db.scalar(select(MatchingStartResult)) is None
        assert db.get(User, user.id) is not None
