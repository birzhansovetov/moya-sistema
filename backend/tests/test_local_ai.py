from dataclasses import replace

from test_onboarding import answers
from test_spheres import sign_in


def test_assist_uses_only_saved_compatible_ids_and_never_starts_plans(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True, local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    health = shown["candidates_by_sphere"]["health"][0]["id"]
    education = shown["candidates_by_sphere"]["education"][0]["id"]
    seen = {}

    def fake_chat(model, prompt):
        seen.update({"model": model, "prompt": prompt})
        return {"recommendations": [
            {"sphere": "health", "id": "invented-program", "why": "Лучший выбор"},
            {"sphere": "education", "id": education, "why": "Подходит под ваш ритм"},
        ]}

    monkeypatch.setattr(local_ai, "_chat", fake_chat)
    assert client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}).status_code == 403
    response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["source"] == "local_ai"
    assert result["recommendations"]["health"]["id"] == health
    assert result["recommendations"]["health"]["source"] == "rules"
    assert result["recommendations"]["education"]["id"] == education
    assert result["recommendations"]["education"]["source"] == "local_ai"
    assert "ai@example.com" not in seen["prompt"]
    assert "correct horse battery staple" not in seen["prompt"]
    assert client.get("/api/health/sport/plan").json()["plan"] is None


def test_assist_falls_back_when_local_model_is_unavailable(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True, local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-fallback@example.com")
    shown = client.post("/api/onboarding/preview", json=answers(), headers={"X-CSRF-Token": csrf}).json()
    monkeypatch.setattr(local_ai, "_chat", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.json()["source"] == "rules"
    assert response.json()["recommendations"]["health"]["id"] == shown["candidates_by_sphere"]["health"][0]["id"]


def test_assist_rejects_foreign_preview(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True, local_ai_enabled=True, environment="development")
    first_csrf = sign_in(client, mailbox, "ai-owner@example.com")
    shown = client.post("/api/onboarding/preview", json=answers(), headers={"X-CSRF-Token": first_csrf}).json()
    other_csrf = sign_in(client, mailbox, "ai-other@example.com")
    response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers={"X-CSRF-Token": other_csrf})
    assert response.status_code == 404


def test_malformed_model_output_cannot_leave_partial_ai_selection(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True, local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-malformed@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    education = shown["candidates_by_sphere"]["education"][0]["id"]
    monkeypatch.setattr(local_ai, "_chat", lambda *_: {"recommendations": [
        {"sphere": "education", "id": education}, {"sphere": [], "id": "bad"}]})
    result = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers).json()
    assert result["source"] == "rules"
    assert all(item["source"] == "rules" for item in result["recommendations"].values())


def test_model_transport_connects_directly_to_loopback_without_proxy(monkeypatch):
    from app import local_ai

    seen = {}

    class Response:
        status = 200

        def read(self):
            return b'{"message":{"content":"{\\"recommendations\\":[]}"}}'

    class Connection:
        def __init__(self, host, port, timeout):
            seen.update(host=host, port=port, timeout=timeout)

        def request(self, method, path, body, headers):
            seen.update(method=method, path=path, body=body, headers=headers)

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(local_ai.http.client, "HTTPConnection", Connection)
    assert local_ai._chat("local-model", "synthetic") == {"recommendations": []}
    assert (seen["host"], seen["port"], seen["path"]) == ("127.0.0.1", 11434, "/api/chat")
    assert b"synthetic" in seen["body"]


def test_assist_caches_successful_response_per_preview(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-cache@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    calls = []

    def fake_chat(model, prompt):
        calls.append(prompt)
        return {"recommendations": [{"sphere": "health", "id": shown["candidates_by_sphere"]["health"][0]["id"]}]}

    monkeypatch.setattr(local_ai, "_chat", fake_chat)
    for _ in range(5):
        response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers)
        assert response.status_code == 200
        assert response.json()["source"] == "local_ai"
    assert len(calls) == 1


def test_assist_limits_failed_model_attempts(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-limit@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    calls = []

    def unavailable(*_):
        calls.append(1)
        raise OSError("offline")

    monkeypatch.setattr(local_ai, "_chat", unavailable)
    for _ in range(5):
        response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers)
        assert response.json()["source"] == "rules"
    assert len(calls) == 3


def test_assist_never_calls_local_model_in_staging(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="staging")
    csrf = sign_in(client, mailbox, "ai-staging@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    calls = []
    monkeypatch.setattr(local_ai, "_chat", lambda *_: calls.append(1))
    response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["source"] == "rules"
    assert not calls


def test_assist_uses_recent_workout_progress_without_private_notes(client, mailbox, monkeypatch):
    import json
    from datetime import timedelta
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.db import utc_now
    from app.models import SportPlan, User, WorkoutLog
    from app.tasks import local_date
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-progress@example.com")
    today = local_date("Asia/Almaty")
    week_end = today - timedelta(days=today.isoweekday())
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "ai-progress@example.com"))
        plan = SportPlan(user_id=user.id, program_id="old-program", content_version="old",
                         answers={}, program_snapshot={"title": "Old"}, active_key=None,
                         started_on=week_end - timedelta(days=14), archived_at=utc_now())
        db.add(plan)
        db.flush()
        db.add(WorkoutLog(user_id=user.id, plan_id=plan.id, workout_date=week_end,
                          session_id="a", results=[], difficulty=8, note="PRIVATE-NOTE"))
        db.commit()
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    prompts = []

    def fake_chat(model, prompt):
        prompts.append(prompt)
        return {"recommendations": [{"sphere": "health", "id": shown["candidates_by_sphere"]["health"][0]["id"]}]}

    monkeypatch.setattr(local_ai, "_chat", fake_chat)
    response = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers)
    assert response.status_code == 200, response.text
    progress = json.loads(prompts[0])["progress"]
    assert progress["health"] == {"workouts": 1, "average_difficulty": 8}
    assert progress["week_end"] == week_end.isoformat()
    assert "PRIVATE-NOTE" not in prompts[0]
    assert "ai-progress@example.com" not in prompts[0]
    assert response.json()["progress_considered"] is True


def test_assist_uses_only_current_plan_feedback_from_last_completed_week(client, mailbox, monkeypatch):
    import json
    from datetime import timedelta
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import SportPlan, TrainingFeedback, User
    from app.tasks import local_date
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-feedback@example.com")
    today = local_date("Asia/Almaty")
    week_end = today - timedelta(days=today.isoweekday())
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "ai-feedback@example.com"))
        old = SportPlan(user_id=user.id, program_id="old", content_version="v1", answers={},
                        program_snapshot={}, active_key=None, started_on=week_end - timedelta(days=28))
        active = SportPlan(user_id=user.id, program_id="active", content_version="v1", answers={},
                           program_snapshot={}, active_key="active", started_on=week_end - timedelta(days=7))
        db.add_all([old, active])
        db.flush()
        db.add_all([
            TrainingFeedback(user_id=user.id, plan_id=old.id, week_end=week_end, rating="too_hard"),
            TrainingFeedback(user_id=user.id, plan_id=active.id, week_end=week_end, rating="too_easy"),
        ])
        db.commit()
    shown = client.post("/api/onboarding/preview", json=answers(), headers={"X-CSRF-Token": csrf}).json()
    prompts = []
    monkeypatch.setattr(local_ai, "_chat", lambda _model, prompt: (prompts.append(prompt) or {"recommendations": []}))
    result = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]},
                         headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200, result.text
    assert json.loads(prompts[0])["progress"]["health"]["feedback"] == "too_easy"
    assert json.loads(prompts[0])["progress"]["health"]["current_program_id"] == "active"
    assert "too_hard" not in prompts[0]


def test_assist_explains_valid_choice_from_weekly_feedback_without_accepting_untrusted_ids(client, mailbox, monkeypatch):
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-weekly-explanation@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    health_id = shown["candidates_by_sphere"]["health"][0]["id"]
    monkeypatch.setattr(local_ai, "_chat", lambda *_: {"recommendations": [
        {"sphere": "health", "id": health_id,
         "why": "После вашей оценки нагрузки стоит проверить эту программу на следующей неделе."},
        {"sphere": "education", "id": "invented", "why": "Недоступный урок"},
    ]})
    result = client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]}, headers=headers).json()
    assert result["recommendations"]["health"]["why"] == (
        "После вашей оценки нагрузки стоит проверить эту программу на следующей неделе.")
    assert result["recommendations"]["education"]["source"] == "rules"


def test_assist_summarizes_failed_learning_skills_without_answers_or_private_text(client, mailbox, monkeypatch):
    import json
    from datetime import timedelta
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import StudyAttempt, StudyPlan, User
    from app.tasks import local_date
    from app import local_ai

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True,
                                        local_ai_enabled=True, environment="development")
    csrf = sign_in(client, mailbox, "ai-skills@example.com")
    end = local_date("Asia/Almaty") - timedelta(days=local_date("Asia/Almaty").isoweekday())
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "ai-skills@example.com"))
        plan = StudyPlan(user_id=user.id, course_id="english", version="v2", active_slot="english",
                         config={}, lesson_ids=["en-a2-01"], create_key="skill-plan", fingerprint="skill-plan")
        db.add(plan)
        db.flush()
        db.add(StudyAttempt(user_id=user.id, plan_id=plan.id, lesson_id="en-a2-01", date=end,
                            snapshot={"quiz": [{"skill": "Present Simple", "prompt": "PRIVATE-QUESTION"}]},
                            result={"feedback": [{"correct": False, "answer": "PRIVATE-ANSWER"}]},
                            passed=False, create_key="skill-attempt", fingerprint="skill-attempt"))
        db.commit()
    shown = client.post("/api/onboarding/preview", json=answers(), headers={"X-CSRF-Token": csrf}).json()
    prompts = []
    monkeypatch.setattr(local_ai, "_chat", lambda _model, prompt: (prompts.append(prompt) or {"recommendations": []}))
    client.post("/api/onboarding/assist", json={"preview_id": shown["preview_id"]},
                headers={"X-CSRF-Token": csrf})
    progress = json.loads(prompts[0])["progress"]
    assert progress["languages"]["weak_skills"] == ["Present Simple"]
    assert "PRIVATE-QUESTION" not in prompts[0]
    assert "PRIVATE-ANSWER" not in prompts[0]
