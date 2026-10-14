from fastapi.testclient import TestClient

from conftest import Mailbox
from test_tasks import create_task, login


def test_rescheduled_completion_history_is_private_to_its_owner(client: TestClient, mailbox: Mailbox) -> None:
    first_csrf = login(client, mailbox, "first@example.com")
    task_id = create_task(client, first_csrf).json()["id"]
    assert client.post(
        f"/api/tasks/{task_id}/occurrences/2026-10-06/complete",
        json={"completed": True},
        headers={"X-CSRF-Token": first_csrf},
    ).status_code == 200
    assert client.patch(
        f"/api/tasks/{task_id}", json={"due_date": "2026-10-07"}, headers={"X-CSRF-Token": first_csrf}
    ).status_code == 200

    login(client, mailbox, "second@example.com")
    assert client.get("/api/calendar?start=2026-10-06&end=2026-10-07").json()["items"] == []

    client.post("/api/auth/login", json={"email": "first@example.com", "password": "correct horse battery staple"})
    history = client.get("/api/calendar?start=2026-10-06&end=2026-10-07").json()["items"]
    assert [(item["date"], item["completed"], item["historical"]) for item in history] == [
        ("2026-10-06", True, True), ("2026-10-07", False, False)
    ]
