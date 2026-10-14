from datetime import date

import pytest

from app.study import course
from app.study_help import get_help_fragment, validate_help_catalog


@pytest.mark.parametrize("course_id,version,lesson_id", [
    ("java", "v2", "java-01"),
    ("go", "v2", "go-01"),
    ("english", "v2", "en-a2-01"),
    ("java-backend", "v3", "backend-01"),
])
def test_first_lessons_have_staged_reviewed_help(course_id, version, lesson_id):
    lesson = course(course_id, version)["lessons"][0]
    for index in range(len(lesson["quiz"])):
        item = get_help_fragment(course_id, version, lesson_id, index, today=date(2026, 10, 14))
        assert item is not None
        assert item.hint and item.next_step and item.explanation
        assert len({item.hint, item.next_step, item.explanation}) == 3
        assert item.version == version and item.lesson_id == lesson_id and item.question_index == index


def test_old_version_is_separate_and_missing_question_returns_none():
    assert get_help_fragment("java", "v1", "java-01", 0, today=date(2026, 10, 14)) is not None
    assert get_help_fragment("java", "v2", "java-01", 99, today=date(2026, 10, 14)) is None
    assert get_help_fragment("java", "v2", "invented", 0, today=date(2026, 10, 14)) is None


def test_catalog_rejects_spoiler_and_malformed_review():
    entry = {"course_id": "java", "course_version": "v2", "lesson_id": "java-01", "question_index": 0,
             "hint": "Компилирует исходник", "next_step": "Дальше", "explanation": "Разбор",
             "review": {"license": "original", "source": "platform", "checked_at": "2026-10-14",
                        "checked_by": "editor", "recheck_by": "2027-04-14"}}
    with pytest.raises(ValueError, match="answer"):
        validate_help_catalog([entry])
    entry["hint"] = "Посмотрите на разницу двух команд."
    entry["review"].pop("license")
    with pytest.raises(ValueError, match="review"):
        validate_help_catalog([entry])


def test_expired_help_is_not_offered():
    assert get_help_fragment("java", "v2", "java-01", 0, today=date(2028, 1, 1)) is None


def test_revoked_help_is_not_offered():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import Base
    from app.models import ContentRevocation

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ContentRevocation(kind="study_help", item_id="java:v2:java-01:0", version="v1",
                                 active=True, reason="Needs review"))
        db.commit()
        assert get_help_fragment("java", "v2", "java-01", 0, today=date(2026, 10, 14), db=db) is None


@pytest.mark.parametrize("course_id,version,lesson_id", [
    ("java", "v2", "java-02"), ("go", "v2", "go-02"),
    ("english", "v2", "en-a2-02"), ("java-backend", "v3", "backend-02"),
])
def test_second_lessons_close_measured_gaps(course_id, version, lesson_id):
    lesson = course(course_id, version)["lessons"][1]
    assert all(get_help_fragment(course_id, version, lesson_id, index, today=date(2026, 10, 14))
               for index in range(len(lesson["quiz"])))
