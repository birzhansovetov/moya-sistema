from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from conftest import Mailbox
from test_spheres import sign_in


def plan_answers(**overrides):
    values = {
        "goal": "fat_loss_muscle_focus", "level": "beginner", "place": "home",
        "equipment": ["bands"], "days_per_week": 2, "minutes_per_session": 35,
        "limitations": False, "weekdays": [1, 4],
    }
    values.update(overrides)
    return values


def test_sport_catalog_and_plan_are_private_and_selected_from_answers(client: TestClient, mailbox: Mailbox) -> None:
    assert client.get("/api/health/sport/catalog").status_code == 401
    csrf = sign_in(client, mailbox, "one@example.com")
    catalog = client.get("/api/health/sport/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["programs"]) >= 56
    assert client.get("/api/health/sport/plan").json()["plan"] is None

    preview = client.post("/api/health/sport/match", json=plan_answers())
    assert preview.status_code == 200
    assert preview.json()["program"]["id"] == "fat_loss_home_beginner_v1"
    assert client.put("/api/health/sport/plan", json={"answers": plan_answers()}).status_code == 403
    saved = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers={"X-CSRF-Token": csrf})
    assert saved.status_code == 200
    assert saved.json()["status"] == "saved"
    assert saved.json()["plan"]["program"]["id"] == "fat_loss_home_beginner_v1"
    assert saved.json()["plan"]["answers"]["weekdays"] == [1, 4]
    sign_in(client, mailbox, "two@example.com")
    assert client.get("/api/health/sport/plan").json()["plan"] is None


def test_outdoor_four_day_program_can_be_saved_and_logged(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "outdoor-four@example.com")
    headers = {"X-CSRF-Token": csrf}
    selected = plan_answers(place="outdoor", equipment=["low_bar", "bench", "bands"],
                            days_per_week=4, weekdays=[1, 2, 4, 6], minutes_per_session=60)
    response = client.put('/api/health/sport/plan', json={"answers": selected}, headers=headers)
    assert response.status_code == 200, response.text
    plan = response.json()['plan']
    assert len(plan['program']['sessions']) == 4
    first = plan['program']['sessions'][0]
    result = {"exercise_id": first['work'][0]['exercise_id'], "completed_sets": 2,
              "reps_per_set": [8, 8]}
    logged = client.post('/api/health/sport/workouts', json={"plan_id": plan['id'],
        "date": plan['started_on'], "session_id": first['id'], "results": [result],
        "difficulty": 5}, headers=headers)
    assert logged.status_code == 201, logged.text
    assert logged.json()['plan_id'] == plan['id']


def test_workout_draft_saves_progress_without_counting_as_completed(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "draft@example.com")
    headers = {"X-CSRF-Token": csrf}
    plan = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    params = {"plan_id": plan["id"], "date": plan["started_on"], "session_id": "A"}
    assert client.get("/api/health/sport/draft", params=params).json()["draft"] is None
    assert client.put("/api/health/sport/draft", json={**params, "actual": {}, "difficulty": 5}).status_code == 403
    assert client.put("/api/health/sport/draft", json={**params, "actual": {"unknown": {"sets": 1, "reps": ["8"], "weight": ""}}, "difficulty": 5}, headers=headers).status_code == 422
    draft = client.put("/api/health/sport/draft", json={**params, "actual": {"chair_squat": {"sets": 2, "reps": ["10", ""], "weight": ""}}, "difficulty": 5, "note": "Первый подход"}, headers=headers)
    assert draft.status_code == 200, draft.text
    assert draft.json()["draft"]["actual"]["chair_squat"]["reps"] == ["10", ""]
    assert client.get("/api/health/sport/draft", params=params).json()["draft"]["note"] == "Первый подход"
    assert client.get("/api/health/sport/workouts").json()["items"] == []
    assert client.put("/api/health/sport/draft", json={**params, "actual": {}, "difficulty": 6, "note": "Продолжение"}, headers=headers).json()["draft"]["note"] == "Продолжение"
    sign_in(client, mailbox, "other-draft@example.com")
    assert client.get("/api/health/sport/draft", params=params).status_code == 404
    csrf = client.post("/api/auth/login", json={"email": "draft@example.com", "password": "correct horse battery staple"}).json()["csrf_token"]
    completed = client.post("/api/health/sport/workouts", json={**params, "results": [{"exercise_id": "chair_squat", "completed_sets": 1, "reps_per_set": [10]}], "difficulty": 6}, headers={"X-CSRF-Token": csrf})
    assert completed.status_code == 201
    assert client.get("/api/health/sport/draft", params=params).json()["draft"] is None
    assert client.put("/api/health/sport/draft", json={**params, "actual": {}, "difficulty": 5}, headers={"X-CSRF-Token": csrf}).status_code == 409
    assert len(client.get("/api/health/sport/workouts").json()["items"]) == 1


def test_replacement_previews_change_and_preserves_old_workout_history(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    first = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    local_today = datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()
    result = {"exercise_id": "chair_squat", "completed_sets": 2, "reps_per_set": [10, 9], "weight_kg": None}
    log_payload = {"plan_id": first["id"], "date": local_today, "session_id": "A", "results": [result], "difficulty": 5, "note": "Комфортно"}
    logged = client.post("/api/health/sport/workouts", json=log_payload, headers=headers)
    assert logged.status_code == 201
    assert client.post("/api/health/sport/workouts", json=log_payload, headers=headers).json()["id"] == logged.json()["id"]
    next_answers = plan_answers(place="gym", equipment=["machines"], minutes_per_session=40)
    preview = client.put("/api/health/sport/plan", json={"answers": next_answers}, headers=headers)
    assert preview.status_code == 200
    assert preview.json()["status"] == "preview"
    assert preview.json()["proposed"]["id"] == "fat_loss_gym_beginner_v1"
    assert client.get("/api/health/sport/plan").json()["plan"]["id"] == first["id"]
    changed = client.put("/api/health/sport/plan", json={"answers": next_answers, "confirm_replace": True}, headers=headers)
    assert changed.status_code == 200
    assert changed.json()["plan"]["id"] != first["id"]
    assert changed.json()["plan"]["program"]["id"] == "fat_loss_gym_beginner_v1"
    logs = client.get("/api/health/sport/workouts").json()["items"]
    assert len(logs) == 1
    assert logs[0]["plan_id"] == first["id"]
    assert logs[0]["results"] == [result]
    assert logs[0]["program_title"] == first["program"]["title"]
    assert logs[0]["session_title"] == first["program"]["sessions"][0]["title"]
    sign_in(client, mailbox, "two@example.com")
    assert client.get("/api/health/sport/workouts").json()["items"] == []


def test_expired_cycle_can_restart_with_same_answers_and_preserve_history(client: TestClient, mailbox: Mailbox, monkeypatch) -> None:
    from app.routes import sport

    csrf = sign_in(client, mailbox, "restart@example.com")
    headers = {"X-CSRF-Token": csrf}
    monkeypatch.setattr(sport, "_today", lambda user: date(2026, 9, 1))
    first = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    payload = {"plan_id": first["id"], "date": "2026-09-01", "session_id": "A", "results": [{"exercise_id": "chair_squat", "completed_sets": 1, "reps_per_set": [10]}], "difficulty": 5}
    assert client.post("/api/health/sport/workouts", json=payload, headers=headers).status_code == 201
    monkeypatch.setattr(sport, "_today", lambda user: date(2026, 10, 6))
    preview = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers)
    assert preview.json()["status"] == "preview"
    assert client.post("/api/health/sport/workouts", json={**payload, "date": "2026-10-06"}, headers=headers).status_code == 422
    restarted = client.put("/api/health/sport/plan", json={"answers": plan_answers(), "confirm_replace": True}, headers=headers).json()
    assert restarted["status"] == "replaced"
    assert restarted["plan"]["id"] != first["id"]
    assert restarted["plan"]["started_on"] == "2026-10-06"
    assert client.get("/api/health/sport/workouts").json()["items"][0]["plan_id"] == first["id"]


def test_sport_rejects_unsupported_plan_and_invalid_workout(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    no_match = client.post("/api/health/sport/match", json=plan_answers(limitations=True))
    assert no_match.status_code == 200
    assert no_match.json()["program"] is None
    assert client.put("/api/health/sport/plan", json={"answers": plan_answers(limitations=True)}, headers=headers).status_code == 422
    plan = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    local_today = datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()
    invalid = {"plan_id": plan["id"], "date": local_today, "session_id": "A", "results": [{"exercise_id": "leg_press", "completed_sets": 2, "reps_per_set": [10, 10]}], "difficulty": 4}
    assert client.post("/api/health/sport/workouts", json=invalid, headers=headers).status_code == 422
    invalid["results"][0]["exercise_id"] = "chair_squat"
    invalid["results"][0]["reps_per_set"] = [10]
    assert client.post("/api/health/sport/workouts", json=invalid, headers=headers).status_code == 422
    assert client.get("/api/health/sport/workouts").json()["items"] == []


def test_workout_retry_normalizes_note_before_comparing(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "retry@example.com")
    headers = {"X-CSRF-Token": csrf}
    plan = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    payload = {"plan_id": plan["id"], "date": plan["started_on"], "session_id": "A", "results": [{"exercise_id": "chair_squat", "completed_sets": 1, "reps_per_set": [10]}], "difficulty": 5, "note": "  Комфортно  "}
    first = client.post("/api/health/sport/workouts", json=payload, headers=headers)
    retry = client.post("/api/health/sport/workouts", json=payload, headers=headers)
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    assert retry.json()["note"] == "Комфортно"


def test_workout_records_only_catalogued_compatible_replacement(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "swap@example.com")
    headers = {"X-CSRF-Token": csrf}
    plan = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    result = {"exercise_id": "chair_squat", "performed_exercise_id": "bodyweight_squat", "completed_sets": 2, "reps_per_set": [10, 10]}
    payload = {"plan_id": plan["id"], "date": plan["started_on"], "session_id": "A", "results": [result], "difficulty": 5}
    saved = client.post("/api/health/sport/workouts", json=payload, headers=headers)
    assert saved.status_code == 201
    assert saved.json()["results"][0]["performed_exercise_id"] == "bodyweight_squat"
    assert saved.json()["results"][0]["performed_exercise_name"] == "Приседание с собственным весом"
    payload["date"] = datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()
    payload["session_id"] = "B"
    payload["results"][0]["performed_exercise_id"] = "leg_press"
    assert client.post("/api/health/sport/workouts", json=payload, headers=headers).status_code == 422
