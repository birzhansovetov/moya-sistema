from test_spheres import sign_in


def answers():
    return {
        "health": {
            "sport": {"goal": "fat_loss_muscle_focus", "level": "beginner", "place": "home", "equipment": [], "days_per_week": 2, "minutes_per_session": 35, "limitations": False, "weekdays": [1, 4]},
            "vegetarian": False,
            "max_cooking_minutes": 45,
            "nutrition_goal": "maintain",
            "allergies": [],
        },
        "education": {"track": "java", "reading_genres": ["classic"], "minutes": 30, "weekdays": [0, 2, 4]},
        "profession": {"track": "java-backend", "minutes": 30, "weekdays": [1, 3]},
        "languages": {"level": "A2", "goal": "general", "minutes": 30, "weekdays": [0, 2, 4]},
        "finance": {"currency": "KZT", "focus": "record"},
        "personal": {"focus": "journal"},
    }


def test_survey_version_is_saved_with_answers(client, mailbox):
    csrf = sign_in(client, mailbox, "version@example.com")
    assert client.get("/api/onboarding").json()["survey_version"] == 2
    assert client.post("/api/onboarding/start", json=answers(), headers={"X-CSRF-Token": csrf}).status_code == 200
    state = client.get("/api/onboarding").json()
    assert state["survey_version"] == 2
    assert state["answers"] == answers()


def test_future_survey_version_requires_reconfirmation(client, mailbox):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import User

    sign_in(client, mailbox, "future@example.com")
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "future@example.com"))
        user.onboarding_answers = answers()
        user.onboarding_version = 3
        db.commit()
    state = client.get("/api/onboarding").json()
    assert state["survey_version"] == 3
    assert state["needs_reconfirmation"] is True


def test_onboarding_previews_six_spheres_and_starts_only_after_confirmation(client, mailbox):
    csrf = sign_in(client, mailbox, "new@example.com")
    assert client.get("/api/auth/me").json()["user"]["onboarding_complete"] is False
    preview = client.post("/api/onboarding/preview", json=answers(), headers={"X-CSRF-Token": csrf})
    assert preview.status_code == 200, preview.text
    areas = preview.json()["areas"]
    assert set(areas) == {"health", "education", "profession", "languages", "finance", "personal"}
    assert areas["health"]["sport"]["status"] == "matched"
    assert areas["education"]["book"] is None
    assert client.get("/api/health/sport/plan").json()["plan"] is None
    assert client.get("/api/study/state/english").json()["active_plan"] is None

    assert client.post("/api/onboarding/start", json=answers()).status_code == 403
    started = client.post("/api/onboarding/start", json=answers(), headers={"X-CSRF-Token": csrf})
    assert started.status_code == 200, started.text
    assert started.json()["user"]["onboarding_complete"] is True
    assert client.get("/api/health/sport/plan").json()["plan"] is not None
    for course in ("java", "java-backend", "english"):
        assert client.get(f"/api/study/state/{course}").json()["active_plan"] is not None
    assert client.get("/api/onboarding").json()["answers"] == answers()
    again = client.post("/api/onboarding/start", json=answers(), headers={"X-CSRF-Token": csrf})
    assert again.status_code == 200
    assert again.json()["status"] == "unchanged"


def test_reading_recommendation_only_appears_for_reading_choices(client, mailbox):
    csrf = sign_in(client, mailbox, "reading-choice@example.com")
    headers = {"X-CSRF-Token": csrf}
    selected = answers()
    for track, expected in (("none", False), ("java", False), ("go", False),
                            ("reading", True), ("both", True), ("go-reading", True)):
        selected["education"]["track"] = track
        response = client.post('/api/onboarding/preview', json=selected, headers=headers)
        assert response.status_code == 200, response.text
        book = response.json()["areas"]["education"]["book"]
        assert bool(book) is expected, track


def test_reading_genres_match_only_tagged_books(client, mailbox):
    csrf = sign_in(client, mailbox, "genre-choice@example.com")
    selected = answers()
    selected["education"]["track"] = "reading"
    selected["education"]["reading_genres"] = ["horror"]
    response = client.post('/api/onboarding/preview', json=selected, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    assert response.json()["areas"]["education"]["book"]["title"] == "Пиковая дама"
    selected["education"]["reading_genres"] = ["detective"]
    response = client.post('/api/onboarding/preview', json=selected, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    assert response.json()["areas"]["education"]["book"] is None
    selected["education"]["reading_genres"] = []
    assert client.post('/api/onboarding/preview', json=selected, headers={"X-CSRF-Token": csrf}).status_code == 422


def test_go_route_previews_and_preserves_java_history_on_switch(client, mailbox):
    csrf = sign_in(client, mailbox, "go@example.com")
    headers = {"X-CSRF-Token": csrf}
    original = answers()
    assert client.post('/api/onboarding/start', json=original, headers=headers).status_code == 200
    java_id = client.get('/api/study/state/java').json()['active_plan']['id']
    selected = answers()
    selected['education']['track'] = 'go-reading'
    preview = client.post('/api/onboarding/preview', json=selected, headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()['areas']['education']['study']['lesson_count'] == 32
    assert preview.json()['areas']['education']['study']['route'] == '/education/go'
    assert client.post('/api/onboarding/start', json=selected, headers=headers).status_code == 409
    saved = client.post('/api/onboarding/start?confirm_replace=true', json=selected, headers=headers)
    assert saved.status_code == 200, saved.text
    assert client.get('/api/study/state/go').json()['active_plan']['course_id'] == 'go'
    assert client.get('/api/study/state/java').json()['active_plan'] is None
    assert client.get('/api/study/state/java?plan_id=' + java_id).json()['plan']['archived']


def test_onboarding_keeps_other_accounts_private_and_reports_unsupported_match(client, mailbox):
    csrf = sign_in(client, mailbox, "first@example.com")
    payload = answers()
    payload["health"]["sport"]["level"] = "intermediate"
    preview = client.post("/api/onboarding/preview", json=payload, headers={"X-CSRF-Token": csrf})
    assert preview.status_code == 200
    assert preview.json()["areas"]["health"]["sport"]["status"] == "unavailable"
    assert preview.json()["areas"]["health"]["sport"]["material"]["route"] == "/health/sport#sport-intermediate"
    assert client.post("/api/onboarding/start", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/health/sport/plan").json()["plan"] is None
    sign_in(client, mailbox, "second@example.com")
    assert client.get("/api/onboarding").json()["answers"] is None
    assert client.get("/api/auth/me").json()["user"]["onboarding_complete"] is False


def test_onboarding_rejects_incomplete_or_invalid_survey(client, mailbox):
    csrf = sign_in(client, mailbox, "new@example.com")
    headers = {"X-CSRF-Token": csrf}
    incomplete = answers()
    del incomplete["personal"]
    assert client.post("/api/onboarding/preview", json=incomplete, headers=headers).status_code == 422
    invalid = answers()
    invalid["languages"]["level"] = "C2"
    assert client.post("/api/onboarding/start", json=invalid, headers=headers).status_code == 422
    assert client.get("/api/auth/me").json()["user"]["onboarding_complete"] is False


def test_skipped_tracks_offer_library_material_without_activating_plans(client, mailbox):
    csrf = sign_in(client, mailbox, "skipped@example.com")
    payload = answers()
    payload["health"]["sport"] = None
    payload["education"]["track"] = "reading"
    payload["profession"]["track"] = "none"
    payload["languages"]["level"] = "none"
    response = client.post("/api/onboarding/preview", json=payload, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    areas = response.json()["areas"]
    assert areas["health"]["sport"]["material"]["route"] == "/health/sport#sport-guides"
    assert areas["education"]["study"]["material"]["route"] == "/education"
    assert areas["profession"]["study"]["material"]["route"] == "/profession"
    assert areas["languages"]["study"]["material"]["route"] == "/languages"
    assert client.post("/api/onboarding/start", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/health/sport/plan").json()["plan"] is None
    for course in ("java", "java-backend", "english"):
        assert client.get(f"/api/study/state/{course}").json()["active_plan"] is None


def test_nutrition_goal_changes_recipe_preview_and_allergies_filter_it(client, mailbox):
    csrf = sign_in(client, mailbox, "recipes@example.com")
    headers = {"X-CSRF-Token": csrf}
    everyday = answers()
    gain = answers()
    gain["health"]["nutrition_goal"] = "gain"
    gain["health"]["allergies"] = ["milk"]
    ordinary = client.post("/api/onboarding/preview", json=everyday, headers=headers)
    selected = client.post("/api/onboarding/preview", json=gain, headers=headers)
    assert ordinary.status_code == selected.status_code == 200
    ordinary_recipes = ordinary.json()["areas"]["health"]["recipes"]
    gain_recipes = selected.json()["areas"]["health"]["recipes"]
    assert gain_recipes["count"] < ordinary_recipes["count"]
    assert gain_recipes["example"] != ordinary_recipes["example"]


def test_opening_saved_survey_does_not_rebuild_recommendations(client, mailbox, monkeypatch):
    from app.routes import onboarding

    csrf = sign_in(client, mailbox, "saved@example.com")
    assert client.post("/api/onboarding/start", json=answers(), headers={"X-CSRF-Token": csrf}).status_code == 200
    monkeypatch.setattr(onboarding, "build_preview", lambda *_: (_ for _ in ()).throw(RuntimeError("preview unavailable")))
    response = client.get("/api/onboarding")
    assert response.status_code == 200
    assert response.json()["answers"] == answers()


def test_onboarding_reselection_requires_confirmation_and_keeps_study_history(client, mailbox):
    csrf = sign_in(client, mailbox, "change@example.com")
    headers = {"X-CSRF-Token": csrf}
    original = answers()
    assert client.post("/api/onboarding/start", json=original, headers=headers).status_code == 200
    old = client.get("/api/study/state/java").json()["active_plan"]["id"]
    finance_only = answers()
    finance_only["finance"]["focus"] = "review"
    assert client.post("/api/onboarding/start", json=finance_only, headers=headers).status_code == 200
    assert client.get("/api/study/state/java").json()["active_plan"]["id"] == old
    changed = answers()
    changed["education"]["track"] = "reading"
    changed["health"]["sport"] = None
    assert client.post("/api/onboarding/start", json=changed, headers=headers).status_code == 409
    assert client.get("/api/study/state/java").json()["active_plan"]["id"] == old
    response = client.post("/api/onboarding/start?confirm_replace=true", json=changed, headers=headers)
    assert response.status_code == 200, response.text
    state = client.get("/api/study/state/java").json()
    assert state["active_plan"] is None
    assert any(item["id"] == old and item["archived"] for item in state["plans"])
    assert client.get("/api/health/sport/plan").json()["plan"] is None
