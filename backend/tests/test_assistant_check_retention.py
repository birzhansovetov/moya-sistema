from datetime import timedelta
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.models import User,AssistantCheckAttempt,StudyAttempt
from app.db import utc_now
from app.cleanup import cleanup_assistant


def test_retention_preserves_main_history(client,monkeypatch):
    now=utc_now()
    monkeypatch.setattr('app.cleanup.utc_now',lambda:now)
    with Session(client.app.state.engine)as db:
        user=User(email='retention@example.com',password_hash='unused');db.add(user);db.flush()
        def attempt(issue,created):return AssistantCheckAttempt(user_id=user.id,issue_id=issue,check_id='check',check_version='v1',digest='a'*64,material={},option_id='a',correct=True,created_at=created)
        db.add_all([attempt('old',now-timedelta(days=30,seconds=1)),attempt('boundary',now-timedelta(days=30))]);db.commit()
        assert cleanup_assistant(db)==1;db.commit()
        assert db.scalar(select(func.count()).select_from(AssistantCheckAttempt))==1
        assert db.scalar(select(func.count()).select_from(StudyAttempt))==0
