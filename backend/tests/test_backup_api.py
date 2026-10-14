from datetime import date
from io import BytesIO

import pytest
import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.backup_archive import open_snapshot, seal_snapshot
from app.backup_upload_limit import MAX_REQUEST_BYTES
from app.models import (
    BackupUse, Expense, ExpenseCategory, NutritionMenu, NutritionProfile,
    PersonalEntry, ReadingBook, ReadingLog, SportPlan, StudyAttempt,
    StudyDraft, StudyPlan, StudyReview, Subtask, Task, TaskCompletion, User,
    WorkoutLog,
)
from conftest import Mailbox
from test_spheres import sign_in


PASSWORD = "correct horse battery staple"
PREFIX = "/api/profile/backup"


def test_upload_is_rejected_before_multipart_parsing(client):
    response = client.post(PREFIX + "/preview", content=b"invalid", headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})
    assert response.status_code == 413
    streamed = client.post(PREFIX + "/preview", content=b"x" * (MAX_REQUEST_BYTES + 1), headers={"Content-Length": "0"})
    assert streamed.status_code == 413
    encoded = client.post(PREFIX + "/%70review", content=b"invalid", headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})
    assert encoded.status_code == 413


def post_archive(client, route, archive: bytes, password=PASSWORD, **extra):
    csrf = extra.pop("csrf")
    return client.post(
        PREFIX + route,
        files={"archive": ("personal.moya-backup", BytesIO(archive), "application/octet-stream")},
        data={"archive_password": password, **extra},
        headers={"X-CSRF-Token": csrf},
    )


def export(client, csrf, password=PASSWORD, preview_token=None):
    path = "/safety-copy" if preview_token else "/export"
    body = {"current_password": password}
    if preview_token:
        body["preview_token"] = preview_token
    return client.post(PREFIX + path, json=body, headers={"X-CSRF-Token": csrf})


def seed_personal(client, email, task_id):
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == email))
        db.add(Task(id=task_id, user_id=user.id, title="Оригинальная задача", description="текст"))
        db.add(Subtask(id=f"sub-{task_id}", task_id=task_id, title="Шаг", position=1, completed=True))
        db.add(TaskCompletion(id=f"done-{task_id}", task_id=task_id, occurrence_date=date(2026, 10, 10)))
        db.add(SportPlan(id=f"sport-{task_id}", user_id=user.id, program_id="home", content_version="v1", answers={"place": "home"}, program_snapshot={"title": "Дом", "sessions": []}, active_key="active", started_on=date(2026, 10, 10)))
        db.add(WorkoutLog(id=f"workout-{task_id}", user_id=user.id, plan_id=f"sport-{task_id}", workout_date=date(2026, 10, 10), session_id="A", results=[], difficulty=4))
        db.add(NutritionProfile(user_id=user.id, answers={"goal": "maintain"}, preferences={"budget": "low"}, estimate_snapshot={"estimate": None, "reasons": [], "sources": {}}))
        db.add(NutritionMenu(id=f"menu-{task_id}", user_id=user.id, active_key="active", start_date=date(2026, 10, 10), days_snapshot=[], profile_snapshot={"estimate": {"target_kcal": 2000}}))
        db.add(PersonalEntry(id=f"entry-{task_id}", user_id=user.id, kind="diary", title="Заметка", body="Личный текст", date=date(2026, 10, 10), create_key=f"entry-{task_id}", create_fingerprint="saved"))
        db.add(ExpenseCategory(id=f"category-{task_id}", user_id=user.id, name="Еда", name_key="еда"))
        db.flush()
        db.add(Expense(id=f"expense-{task_id}", user_id=user.id, category_id=f"category-{task_id}", amount_minor=13500, currency="KZT", expense_date=date(2026, 10, 10), create_key=f"expense-{task_id}", create_fingerprint="saved"))
        db.add(ReadingBook(id=f"book-{task_id}", user_id=user.id, title="Книга", pages=200, create_key=f"book-{task_id}", create_fingerprint="saved"))
        db.add(StudyPlan(id=f"study-{task_id}", user_id=user.id, course_id="java", version="v1", active_slot="java", config={"days": [1]}, lesson_ids=["java-1"], create_key=f"study-{task_id}", fingerprint="saved"))
        db.flush()
        db.add(ReadingLog(id=f"log-{task_id}", book_id=f"book-{task_id}", date=date(2026, 10, 10), text="Заметка", create_key=f"log-{task_id}", create_fingerprint="saved"))
        db.add(StudyAttempt(id=f"attempt-{task_id}", user_id=user.id, plan_id=f"study-{task_id}", lesson_id="java-1", date=date(2026, 10, 10), snapshot={"title": "Java"}, result={"score": 1}, passed=True, create_key=f"attempt-{task_id}", fingerprint="saved"))
        db.add(StudyDraft(id=f"draft-{task_id}", user_id=user.id, plan_id=f"study-{task_id}", lesson_id="java-1", content={"note": "черновик"}))
        db.add(StudyReview(id=f"review-{task_id}", user_id=user.id, course_id="java", version="v1", card_id="card-1", rating="good", streak=2, date=date(2026, 10, 10), due_date=date(2026, 10, 12), create_key=f"review-{task_id}", fingerprint="saved"))
        db.commit()
        return user.id, user.password_hash


def test_export_preview_safety_copy_restore_replaces_only_current_account(client, mailbox: Mailbox):
    assert export(client, "wrong").status_code == 401
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    user_id, password_hash = seed_personal(client, "one@example.com", "task-one")
    assert export(client, "wrong").status_code == 403
    encrypted = export(client, csrf)
    assert encrypted.status_code == 200
    assert encrypted.headers["content-type"] == "application/octet-stream"
    original = encrypted.content
    assert "Оригинальная задача".encode() not in original
    assert len(open_snapshot(original, PASSWORD)["tables"]["expenses"]) == 1
    other_csrf = sign_in(client, mailbox, "two@example.com")
    seed_personal(client, "two@example.com", "task-two")
    assert post_archive(client, "/preview", original, csrf=other_csrf).status_code == 422
    csrf = client.post("/api/auth/login", json={"email": "one@example.com", "password": PASSWORD}).json()["csrf_token"]
    with client.app.state.sessionmaker() as db:
        task = db.get(Task, "task-one")
        task.title = "Новая версия"
        db.commit()
    preview = post_archive(client, "/preview", original, csrf=csrf)
    assert preview.status_code == 200
    assert preview.json()["counts"]["tasks"] == 1
    assert preview.json()["created_at"]
    assert preview.json()["preview_token"]
    safety = export(client, csrf, preview_token=preview.json()["preview_token"])
    assert safety.status_code == 200
    assert safety.headers["X-Restore-Token"]
    claims = jwt.decode(safety.headers["X-Restore-Token"], client.app.state.settings.jwt_secret, algorithms=["HS256"])
    assert len(claims["jti"]) <= BackupUse.__table__.c.id.type.length
    assert open_snapshot(safety.content, PASSWORD)["tables"]["tasks"][0]["title"] == "Новая версия"
    restored = post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=safety.headers["X-Restore-Token"])
    assert restored.status_code == 200
    with client.app.state.sessionmaker() as db:
        assert db.get(Task, "task-one").title == "Оригинальная задача"
        assert db.get(Task, "task-two").title == "Оригинальная задача"
        assert db.get(Expense, "expense-task-one").amount_minor == 13500
        assert db.get(ReadingLog, "log-task-one").text == "Заметка"
        assert db.get(Subtask, "sub-task-one").completed is True
        assert db.get(TaskCompletion, "done-task-one").occurrence_date == date(2026, 10, 10)
        assert db.get(WorkoutLog, "workout-task-one").difficulty == 4
        assert db.get(StudyAttempt, "attempt-task-one").result["score"] == 1
        assert db.get(StudyDraft, "draft-task-one").content["note"] == "черновик"
        assert db.get(User, user_id).password_hash == password_hash
    assert client.get("/api/profile").status_code == 200
    assert post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=safety.headers["X-Restore-Token"]).status_code == 409


def test_restore_requires_fresh_safety_copy_and_unchanged_state(client, mailbox: Mailbox):
    csrf = sign_in(client, mailbox, "one@example.com")
    seed_personal(client, "one@example.com", "task-one")
    original = export(client, csrf).content
    preview = post_archive(client, "/preview", original, csrf=csrf).json()
    assert post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=preview["preview_token"]).status_code in (400, 409, 422)
    safety = export(client, csrf, preview_token=preview["preview_token"])
    assert safety.status_code == 200
    with client.app.state.sessionmaker() as db:
        db.get(Task, "task-one").title = "Изменено после копии"
        db.commit()
    stale = post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=safety.headers["X-Restore-Token"])
    assert stale.status_code == 409
    with client.app.state.sessionmaker() as db:
        assert db.get(Task, "task-one").title == "Изменено после копии"


def test_bad_password_and_file_rejected_without_mutation(client, mailbox: Mailbox):
    csrf = sign_in(client, mailbox, "one@example.com")
    seed_personal(client, "one@example.com", "task-one")
    original = export(client, csrf).content
    wrong = post_archive(client, "/preview", original, password="wrong-old-password", csrf=csrf)
    changed = bytearray(original); changed[-1] ^= 1
    tampered = post_archive(client, "/preview", bytes(changed), csrf=csrf)
    assert wrong.status_code == tampered.status_code == 422
    assert wrong.json()["detail"] == tampered.json()["detail"]
    assert post_archive(client, "/preview", b"x" * (8 * 1024 * 1024 + 1), csrf=csrf).status_code == 413
    assert export(client, csrf, password="wrong-current-password").status_code == 403
    with client.app.state.sessionmaker() as db:
        assert db.get(Task, "task-one").title == "Оригинальная задача"


def test_restore_accepts_old_archive_password_after_account_password_reset(client, mailbox: Mailbox):
    csrf = sign_in(client, mailbox, "one@example.com")
    seed_personal(client, "one@example.com", "task-one")
    original = export(client, csrf).content
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "one@example.com"))
        from app.auth import password_hash
        user.password_hash = password_hash("new-correct-account-password")
        db.commit()
    preview = post_archive(client, "/preview", original, csrf=csrf).json()
    safety = export(client, csrf, password="new-correct-account-password", preview_token=preview["preview_token"])
    assert safety.status_code == 200
    restored = post_archive(client, "/restore", original, csrf=csrf, current_password="new-correct-account-password", restore_token=safety.headers["X-Restore-Token"])
    assert restored.status_code == 200
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "new-correct-account-password"}).status_code == 200


def test_mid_restore_failure_rolls_back_everything_and_keeps_token_reusable(client, mailbox: Mailbox, monkeypatch):
    csrf = sign_in(client, mailbox, "one@example.com")
    seed_personal(client, "one@example.com", "task-one")
    original = export(client, csrf).content
    with client.app.state.sessionmaker() as db:
        db.get(Task, "task-one").title = "Текущие данные"
        db.commit()
    preview = post_archive(client, "/preview", original, csrf=csrf).json()
    safety = export(client, csrf, preview_token=preview["preview_token"])
    token = safety.headers["X-Restore-Token"]
    from app.routes import backup
    real_replace = backup._replace_personal

    def fail_after_changes(db, user_id, saved):
        real_replace(db, user_id, saved)
        raise IntegrityError("injected", {}, RuntimeError("injected"))

    monkeypatch.setattr(backup, "_replace_personal", fail_after_changes)
    failed = post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=token)
    assert failed.status_code == 422
    with client.app.state.sessionmaker() as db:
        assert db.get(Task, "task-one").title == "Текущие данные"
    monkeypatch.setattr(backup, "_replace_personal", real_replace)
    assert post_archive(client, "/restore", original, csrf=csrf, current_password=PASSWORD, restore_token=token).status_code == 200


def test_preview_rejects_archive_with_broken_foreign_reference(client, mailbox: Mailbox):
    csrf = sign_in(client, mailbox, "one@example.com")
    seed_personal(client, "one@example.com", "task-one")
    saved = open_snapshot(export(client, csrf).content, PASSWORD)
    saved["tables"]["expenses"][0]["category_id"] = "not-in-archive"
    malformed = seal_snapshot(saved, PASSWORD)
    assert post_archive(client, "/preview", malformed, csrf=csrf).status_code == 422
    with client.app.state.sessionmaker() as db:
        assert db.get(Task, "task-one").title == "Оригинальная задача"
