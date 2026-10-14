from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SportPlan, User, WorkoutLog
from conftest import Mailbox
from test_tasks import create_task, login


def test_four_week_analytics_counts_distinct_active_days_and_isolates_accounts(client, mailbox: Mailbox):
    csrf = login(client, mailbox, "analytics-one@example.com")
    task_id = create_task(client, csrf).json()["id"]
    assert client.post(f"/api/tasks/{task_id}/occurrences/2026-10-06/complete",
                       json={"completed": True}, headers={"X-CSRF-Token": csrf}).status_code == 200
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "analytics-one@example.com"))
        plan = SportPlan(user_id=user.id, program_id="sample", content_version="v1",
                         answers={"weekdays": [1, 4]},
                         program_snapshot={"title": "Две тренировки", "duration_weeks": 4,
                                           "sessions": [{"id": "a"}, {"id": "b"}]},
                         active_key="active", started_on=date(2026, 10, 5))
        db.add(plan)
        db.flush()
        db.add(WorkoutLog(user_id=user.id, plan_id=plan.id, workout_date=date(2026, 10, 6),
                          session_id="a", results=[], difficulty=6, note="PRIVATE-NOTE"))
        db.commit()
    result = client.get("/api/calendar/analytics?end=2026-10-11")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["start"] == "2026-09-14"
    assert data["end"] == "2026-10-11"
    assert len(data["weeks"]) == 4
    assert data["summary"]["active_days"] == 1
    assert data["summary"]["workouts_logged"] == 1
    assert data["summary"]["tasks"] == {"planned": 1, "completed": 1}
    assert data["summary"]["areas"]["health"] == 1
    assert data["weeks"][-1]["areas"]["health"] == 1
    assert data["weeks"][-1]["active_days"] == 1
    assert "PRIVATE-NOTE" not in result.text

    login(client, mailbox, "analytics-two@example.com")
    other = client.get("/api/calendar/analytics?end=2026-10-11").json()
    assert other["summary"]["active_days"] == 0
    assert other["summary"]["workouts_logged"] == 0
    assert all(value == 0 for value in other["summary"]["areas"].values())


def test_four_week_analytics_rejects_future_or_non_week_end(client, mailbox: Mailbox):
    login(client, mailbox, "analytics-invalid@example.com")
    assert client.get("/api/calendar/analytics?end=2099-01-04").status_code == 422
    assert client.get("/api/calendar/analytics?end=2026-10-10").status_code == 422
