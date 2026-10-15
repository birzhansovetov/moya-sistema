"""Scheduled cleanup for short-lived matching service data."""

import argparse
import logging
from datetime import timedelta

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import sqlalchemy_url, utc_now
from app.models import MatchingPreview, MatchingStartResult, AssistantRequest, AssistantCheckAttempt

logger = logging.getLogger(__name__)


def cleanup_onboarding(db: Session) -> tuple[int, int]:
    now = utc_now()
    results = db.execute(delete(MatchingStartResult).where(MatchingStartResult.created_at < now - timedelta(days=7))).rowcount
    previews = db.execute(delete(MatchingPreview).where(MatchingPreview.expires_at < now - timedelta(days=1),
        )).rowcount
    return previews, results


def cleanup_assistant(db: Session) -> int:
    checks = db.execute(delete(AssistantCheckAttempt).where(AssistantCheckAttempt.created_at < utc_now()-timedelta(days=30))).rowcount
    return checks + db.execute(delete(AssistantRequest).where(AssistantRequest.created_at < utc_now()-timedelta(days=30))).rowcount


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("area", choices=("onboarding", "assistant"))
    args = parser.parse_args()
    engine = create_engine(sqlalchemy_url(Settings.from_env().database_url))
    try:
        with Session(engine) as db:
            if args.area == "assistant":
                count = cleanup_assistant(db)
                db.commit()
                logger.info("Assistant cleanup: %s records", count)
                return
            previews, results = cleanup_onboarding(db)
            db.commit()
            logger.info("Matching cleanup: %s previews, %s results", previews, results)
    except Exception:
        logger.exception("Matching cleanup failed")
        raise


if __name__ == "__main__":
    main()
