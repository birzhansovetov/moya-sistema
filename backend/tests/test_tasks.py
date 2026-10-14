from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from conftest import Mailbox


def login(client: TestClient, mailbox: Mailbox, email: str) -> str:
    password = "correct horse battery staple"
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    link = next(part for part in mailbox.messages[-1].text.split() if part.startswith("https://"))
    token = parse_qs(urlparse(link).fragment)["token"][0]
    assert client.post("/api/auth/verify", json={"token": token, "password": password}).status_code == 204
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def create_task(client: TestClient, csrf: str, key: str = "task-key-1", **changes):
    payload = {
        "title": "Пробежка",
        "description": "Парк",
        "section": "sport",
        "due_date": "2026-10-06",
        "priority": "high",
        "recurrence": "none",
        "subtasks": ["Взять воду", "Разминка"],
    }
    payload.update(changes)
    return client.post("/api/tasks", json=payload, headers={"X-CSRF-Token": csrf, "Idempotency-Key": key})


def test_create_is_idempotent_and_subtasks_persist(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    first = create_task(client, csrf)
    assert first.status_code == 201
    again = create_task(client, csrf)
    assert again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    tasks = client.get("/api/tasks").json()["items"]
    assert len(tasks) == 1
    assert tasks[0]["priority"] == "high"
    assert len(tasks[0]["subtasks"]) == 2


def test_reused_create_key_rejects_changed_payload(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    assert create_task(client, csrf).status_code == 201
    changed = create_task(client, csrf, title="Другая пробежка")
    assert changed.status_code == 409
    assert len(client.get("/api/tasks").json()["items"]) == 1


def test_task_edit_subtask_and_delete(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task = create_task(client, csrf).json()
    task_id = task["id"]
    changed = client.patch(
        f"/api/tasks/{task_id}", json={"title": "Ходьба", "status": "in_progress", "due_date": "2026-10-07"},
        headers={"X-CSRF-Token": csrf},
    )
    assert changed.status_code == 200
    assert changed.json()["title"] == "Ходьба"
    assert changed.json()["due_date"] == "2026-10-07"
    subtask_id = task["subtasks"][0]["id"]
    done = client.patch(
        f"/api/tasks/{task_id}/subtasks/{subtask_id}", json={"completed": True}, headers={"X-CSRF-Token": csrf}
    )
    assert done.status_code == 200
    assert done.json()["completed"] is True
    assert client.delete(f"/api/tasks/{task_id}", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_board_status_and_calendar_completion_agree_for_one_time_task(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task_id = create_task(client, csrf).json()["id"]
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    items = client.get("/api/calendar?start=2026-10-06&end=2026-10-06").json()["items"]
    assert items[0]["completed"] is True
    assert client.patch(f"/api/tasks/{task_id}", json={"due_date": "2026-10-07"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    old = client.get("/api/calendar?start=2026-10-06&end=2026-10-06").json()["items"]
    new = client.get("/api/calendar?start=2026-10-07&end=2026-10-07").json()["items"]
    assert old[0]["completed"] is True
    assert old[0]["historical"] is True
    assert new[0]["completed"] is False
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "todo"


def test_edit_form_move_does_not_complete_new_date(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task = create_task(client, csrf).json()
    task_id = task["id"]
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    moved = client.patch(f"/api/tasks/{task_id}", json={
        "title": task["title"], "description": task["description"], "section": task["section"],
        "due_date": "2026-10-07", "priority": task["priority"], "status": "done", "recurrence": "none",
    }, headers={"X-CSRF-Token": csrf})
    assert moved.status_code == 200
    assert moved.json()["status"] == "todo"
    items = client.get("/api/calendar?start=2026-10-06&end=2026-10-07").json()["items"]
    assert [(item["date"], item["completed"], item["historical"]) for item in items] == [
        ("2026-10-06", True, True), ("2026-10-07", False, False)
    ]


def test_changing_recurrence_keeps_completed_history(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task_id = create_task(client, csrf, recurrence="daily").json()["id"]
    for day in ["2026-10-06", "2026-10-07"]:
        assert client.post(f"/api/tasks/{task_id}/occurrences/{day}/complete", json={"completed": True}, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.patch(f"/api/tasks/{task_id}", json={"recurrence": "none", "due_date": "2026-10-09"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    items = client.get("/api/calendar?start=2026-10-06&end=2026-10-09").json()["items"]
    assert [(item["date"], item["completed"], item["historical"]) for item in items] == [
        ("2026-10-06", True, True), ("2026-10-07", True, True), ("2026-10-09", False, False)
    ]


def test_subtasks_can_be_added_completed_and_removed(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task_id = create_task(client, csrf).json()["id"]
    added = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Растяжка"}, headers={"X-CSRF-Token": csrf})
    assert added.status_code == 201
    subtask_id = added.json()["id"]
    assert client.patch(f"/api/tasks/{task_id}/subtasks/{subtask_id}", json={"completed": True}, headers={"X-CSRF-Token": csrf}).json()["completed"] is True
    assert client.delete(f"/api/tasks/{task_id}/subtasks/{subtask_id}", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert all(item["id"] != subtask_id for item in client.get(f"/api/tasks/{task_id}").json()["subtasks"])


def test_account_cannot_read_or_change_another_accounts_tasks(client: TestClient, mailbox: Mailbox) -> None:
    first_csrf = login(client, mailbox, "one@example.com")
    task_id = create_task(client, first_csrf).json()["id"]
    second_csrf = login(client, mailbox, "two@example.com")
    assert client.get("/api/tasks").json()["items"] == []
    assert client.get(f"/api/tasks/{task_id}").status_code == 404
    assert client.patch(f"/api/tasks/{task_id}", json={"title": "Чужая"}, headers={"X-CSRF-Token": second_csrf}).status_code == 404
    assert client.post(f"/api/tasks/{task_id}/occurrences/2026-10-06/complete", json={"completed": True}, headers={"X-CSRF-Token": second_csrf}).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers={"X-CSRF-Token": second_csrf}).status_code == 404


def test_daily_occurrences_complete_separately_and_missed_days_are_visible(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    task_id = create_task(client, csrf, recurrence="daily").json()["id"]
    complete = client.post(f"/api/tasks/{task_id}/occurrences/2026-10-06/complete", json={"completed": True}, headers={"X-CSRF-Token": csrf})
    assert complete.status_code == 200
    calendar = client.get("/api/calendar?start=2026-10-06&end=2026-10-08").json()["items"]
    assert [(item["date"], item["completed"]) for item in calendar] == [
        ("2026-10-06", True), ("2026-10-07", False), ("2026-10-08", False)
    ]
    assert client.post(f"/api/tasks/{task_id}/occurrences/2026-10-09/complete", json={"completed": False}, headers={"X-CSRF-Token": csrf}).status_code == 200


def test_weekly_and_selected_weekdays_expand_in_calendar(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, "one@example.com")
    create_task(client, csrf, key="weekly-key", title="Неделя", recurrence="weekly")
    create_task(client, csrf, key="weekdays-key", title="Будни", recurrence="weekdays", weekdays=[0, 2])
    dates = client.get("/api/calendar?start=2026-10-05&end=2026-10-13").json()["items"]
    weekly = [item["date"] for item in dates if item["title"] == "Неделя"]
    weekdays = [item["date"] for item in dates if item["title"] == "Будни"]
    assert weekly == ["2026-10-06", "2026-10-13"]
    assert weekdays == ["2026-10-07", "2026-10-12"]


def test_local_today_uses_profile_timezone() -> None:
    from app.tasks import local_date

    instant = datetime(2026, 10, 5, 20, 30, tzinfo=timezone.utc)
    assert local_date("Asia/Almaty", instant) == date(2026, 10, 6)
    assert local_date("America/New_York", instant) == date(2026, 10, 5)
