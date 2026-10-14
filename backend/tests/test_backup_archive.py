from copy import deepcopy
from datetime import date
import json

import pytest
from sqlalchemy import select

from app.backup_archive import (
    ArchiveError,
    PERSONAL_TABLES,
    open_snapshot,
    seal_snapshot,
    snapshot_user,
    validate_snapshot,
)
from app.models import Expense, ExpenseCategory, Income, Task, User
from conftest import Mailbox
from test_spheres import sign_in


EXPECTED_TABLES = {
    "tasks", "subtasks", "task_completions", "sport_plans", "workout_logs", "workout_drafts",
    "nutrition_profiles", "nutrition_menus", "food_logs", "weight_logs",
    "expense_categories", "expenses", "incomes", "personal_entries", "reading_books",
    "reading_logs", "study_plans", "study_attempts", "study_drafts", "study_reviews", "training_feedback",
}


def empty_snapshot(email="one@example.com"):
    return {
        "schema_version": 1,
        "created_at": "2026-10-10T00:00:00",
        "email": email,
        "source_user_id": "owner-1",
        "profile": {"name": "Тест", "timezone": "Asia/Almaty", "hidden_sections": [], "hidden_spheres": [], "finance_currency": "KZT"},
        "tables": {name: [] for name in EXPECTED_TABLES},
    }


def test_encrypted_archive_roundtrip_and_tamper_rejection():
    value = empty_snapshot()
    value["tables"]["tasks"].append({"id": "task-1", "user_id": "owner-1", "title": "Личная задача"})
    archive = seal_snapshot(value, "старый-пароль-для-архива")
    assert "Личная задача".encode() not in archive
    assert open_snapshot(archive, "старый-пароль-для-архива") == value
    assert seal_snapshot(value, "старый-пароль-для-архива") != archive
    with pytest.raises(ArchiveError):
        open_snapshot(archive, "другой-пароль-для-архива")
    changed = bytearray(archive)
    changed[-1] ^= 1
    with pytest.raises(ArchiveError):
        open_snapshot(bytes(changed), "старый-пароль-для-архива")
    with pytest.raises(ArchiveError):
        open_snapshot(archive[:5] + bytes([255]) + archive[6:], "старый-пароль-для-архива")
    with pytest.raises(ArchiveError):
        open_snapshot(b"x" * (8 * 1024 * 1024 + 1), "старый-пароль-для-архива")


def test_snapshot_covers_all_personal_tables_but_no_auth_secrets(client, mailbox: Mailbox):
    sign_in(client, mailbox, "one@example.com")
    app = client.app
    with app.state.sessionmaker() as db:
        one = db.scalar(select(User).where(User.email == "one@example.com"))
        db.add(Task(id="task-one", user_id=one.id, title="Моя задача", description="секретная заметка"))
        db.add(ExpenseCategory(id="category-one", user_id=one.id, name="Еда", name_key="еда"))
        db.flush()
        db.add(Expense(id="expense-one", user_id=one.id, category_id="category-one", amount_minor=12345, currency="KZT", expense_date=date(2026, 10, 10), create_key="expense-key", create_fingerprint="fingerprint"))
        db.add(Income(id="income-one", user_id=one.id, amount_minor=20000, currency="KZT", source="Работа", income_date=date(2026, 10, 10), create_key="income-key", create_fingerprint="fingerprint"))
        db.commit()
        snapshot = snapshot_user(db, one)
    assert set(PERSONAL_TABLES) == EXPECTED_TABLES
    assert set(snapshot["tables"]) == EXPECTED_TABLES
    assert snapshot["tables"]["tasks"][0]["title"] == "Моя задача"
    assert snapshot["tables"]["expenses"][0]["amount_minor"] == 12345
    assert snapshot["tables"]["expenses"][0]["expense_date"] == "2026-10-10"
    assert snapshot["tables"]["incomes"][0]["amount_minor"] == 20000
    assert "password_hash" not in json.dumps(snapshot)
    assert "login_sessions" not in snapshot["tables"]
    sign_in(client, mailbox, "two@example.com")
    with app.state.sessionmaker() as db:
        two = db.scalar(select(User).where(User.email == "two@example.com"))
        other = snapshot_user(db, two)
    assert not other["tables"]["tasks"] and not other["tables"]["expenses"]


def test_validation_rejects_foreign_email_unknown_fields_and_broken_links():
    value = empty_snapshot()
    assert validate_snapshot(value, "one@example.com")["email"] == "one@example.com"
    with pytest.raises(ArchiveError):
        validate_snapshot(value, "two@example.com")
    bad = deepcopy(value)
    bad["profile"]["password_hash"] = "must-not-import"
    with pytest.raises(ArchiveError):
        validate_snapshot(bad, "one@example.com")
    bad = deepcopy(value)
    bad["tables"]["expenses"] = [{"id": "expense-1", "user_id": "owner-1", "category_id": "missing"}]
    with pytest.raises(ArchiveError):
        validate_snapshot(bad, "one@example.com")
    bad = deepcopy(value)
    bad["tables"]["tasks"] = [{"id": "same", "user_id": "owner-1"}, {"id": "same", "user_id": "owner-1"}]
    with pytest.raises(ArchiveError):
        validate_snapshot(bad, "one@example.com")


def test_archive_before_income_feature_restores_with_empty_incomes():
    old = empty_snapshot()
    del old["tables"]["incomes"]
    checked = validate_snapshot(old, "one@example.com")
    assert checked["tables"]["incomes"] == []


def test_validation_rejects_unusable_profile_settings():
    bad = empty_snapshot()
    bad["profile"]["timezone"] = "Mars/Olympus"
    with pytest.raises(ArchiveError):
        validate_snapshot(bad, "one@example.com")


def test_training_feedback_is_in_archive_and_older_archive_without_it_still_opens(client, mailbox):
    from app.models import SportPlan, TrainingFeedback

    sign_in(client, mailbox, "feedback-archive@example.com")
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "feedback-archive@example.com"))
        plan = SportPlan(user_id=user.id, program_id="sample", content_version="v1", answers={},
                         program_snapshot={}, active_key="active", started_on=date(2026, 10, 5))
        db.add(plan)
        db.flush()
        db.add(TrainingFeedback(user_id=user.id, plan_id=plan.id,
                                week_end=date(2026, 10, 11), rating="too_easy"))
        db.commit()
        snapshot = snapshot_user(db, user)
    assert snapshot["tables"]["training_feedback"][0]["rating"] == "too_easy"
    assert validate_snapshot(snapshot, "feedback-archive@example.com")["tables"]["training_feedback"][0]["rating"] == "too_easy"
    older = deepcopy(snapshot)
    del older["tables"]["training_feedback"]
    assert validate_snapshot(older, "feedback-archive@example.com")["tables"]["training_feedback"] == []


def test_workout_draft_is_archived_and_old_archive_can_omit_it(client, mailbox):
    from app.models import SportPlan, WorkoutDraft

    sign_in(client, mailbox, "draft-archive@example.com")
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "draft-archive@example.com"))
        plan = SportPlan(user_id=user.id, program_id="sample", content_version="v1", answers={},
                         program_snapshot={}, active_key="active", started_on=date(2026, 10, 5))
        db.add(plan)
        db.flush()
        db.add(WorkoutDraft(user_id=user.id, plan_id=plan.id, workout_date=date(2026, 10, 5),
                            session_id="A", actual={"squat": {"sets": 1, "reps": ["8"], "weight": ""}},
                            difficulty=5, note="Начато"))
        db.commit()
        snapshot = snapshot_user(db, user)
    assert validate_snapshot(snapshot, "draft-archive@example.com")["tables"]["workout_drafts"][0]["note"] == "Начато"
    older = deepcopy(snapshot)
    del older["tables"]["workout_drafts"]
    assert validate_snapshot(older, "draft-archive@example.com")["tables"]["workout_drafts"] == []
    bad = empty_snapshot()
    bad["profile"]["hidden_spheres"] = ["secret-admin"]
    with pytest.raises(ArchiveError):
        validate_snapshot(bad, "one@example.com")
