from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, utc_now
from app.models import User
from app.models import StudyPlan
from sqlalchemy import select
from app.preview_store import create_preview, load_preview
from app.content_admin import change_revocation
from app.sport import load_sport_catalog
from dataclasses import replace
from test_onboarding import answers
from test_spheres import sign_in


def test_opaque_preview_owner_and_expiry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'preview.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(email="owner@example.com", password_hash="x")
        other = User(email="other@example.com", password_hash="x")
        db.add_all((owner, other))
        db.flush()
        raw, preview = create_preview(db, owner, {"health": {}}, {"areas": {}, "candidates_by_sphere": {}})
        db.commit()
        assert len(raw) >= 40
        assert raw not in preview.nonce_hash
        assert load_preview(db, owner.id, raw).id == preview.id
        assert load_preview(db, other.id, raw) is None
        preview.expires_at = utc_now() - timedelta(seconds=1)
        db.flush()
        assert load_preview(db, owner.id, raw) is None


def test_preview_api_full_choices_and_rate_limit(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "preview@example.com")
    headers = {"X-CSRF-Token": csrf}
    assert client.post("/api/onboarding/preview", json=answers()).status_code == 403
    first = client.post("/api/onboarding/preview", json=answers(), headers=headers)
    assert first.status_code == 200
    data = first.json()
    assert data["preview_id"]
    full = client.post("/api/onboarding/preview/choices", json={"preview_id": data["preview_id"]}, headers=headers)
    assert full.status_code == 200
    assert len(full.json()["candidates_by_sphere"]["health"]) >= len(data["candidates_by_sphere"]["health"])
    for _ in range(19):
        assert client.post("/api/onboarding/preview", json=answers(), headers=headers).status_code == 200
    limited = client.post("/api/onboarding/preview", json=answers(), headers=headers)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "3600"


def test_selected_start_is_idempotent_and_rejects_outside_choice(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "start@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    preview_id = shown["preview_id"]
    bad = client.post("/api/onboarding/start", json={"preview_id": preview_id, "selected": {"health": "made-up"},
                                                     "skipped": ["education", "profession", "languages", "finance", "personal"],
                                                     "confirm_replace": False}, headers=headers)
    assert bad.status_code == 409
    chosen = {sphere: items[0]["id"] for sphere, items in shown["candidates_by_sphere"].items() if items and sphere != "health_recipes"}
    payload = {"preview_id": preview_id, "selected": chosen,
               "skipped": [sphere for sphere in ("health", "education", "profession", "languages", "finance", "personal") if sphere not in chosen],
               "confirm_replace": False}
    first = client.post("/api/onboarding/start", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    again = client.post("/api/onboarding/start", json=payload, headers=headers)
    assert again.status_code == 200
    assert again.json() == first.json()
    result = client.post("/api/onboarding/result", json={"preview_id": preview_id}, headers=headers)
    assert result.json()["committed"] is True
    assert result.json()["result"] == first.json()
    altered = client.post("/api/onboarding/start", json={**payload, "selected": {}}, headers=headers)
    assert altered.status_code == 409


def test_restore_archived_sport_plan_within_seven_days(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "restore@example.com")
    headers = {"X-CSRF-Token": csrf}
    first_preview = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    first_id = first_preview["candidates_by_sphere"]["health"][0]["id"]
    base = {"selected": {"health": first_id}, "skipped": ["education", "profession", "languages", "finance", "personal"]}
    first = client.post("/api/onboarding/start", json={"preview_id": first_preview["preview_id"], **base}, headers=headers)
    assert first.status_code == 200
    original_id = first.json()["created"]["health"]
    second_preview = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    other_id = next(item["id"] for item in second_preview["candidates_by_sphere"]["health"] if item["id"] != first_id)
    second = client.post("/api/onboarding/start", json={"preview_id": second_preview["preview_id"],
        "selected": {"health": other_id}, "skipped": base["skipped"], "confirm_replace": True}, headers=headers)
    assert second.status_code == 200, second.text
    restored = client.post("/api/onboarding/restore", json={"kind": "sport", "plan_id": original_id,
        "confirm_progress": True}, headers=headers)
    assert restored.status_code == 200, restored.text
    assert client.get("/api/health/sport/plan").json()["plan"]["id"] == original_id


def test_revocation_after_preview_blocks_start_without_archiving(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "revoked-preview@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    item_id = shown["candidates_by_sphere"]["health"][0]["id"]
    with client.app.state.sessionmaker() as db:
        change_revocation(db, "revoke", "sport", item_id, load_sport_catalog()["version"], "Safety review", "operator")
        db.commit()
    attempted = client.post("/api/onboarding/start", json={"preview_id": shown["preview_id"],
        "selected": {"health": item_id}, "skipped": ["education", "profession", "languages", "finance", "personal"]}, headers=headers)
    assert attempted.status_code == 409
    assert client.get("/api/health/sport/plan").json()["plan"] is None


def test_skipping_health_keeps_existing_plan_while_starting_study(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "skip@example.com")
    headers = {"X-CSRF-Token": csrf}
    first = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    sport_id = first["candidates_by_sphere"]["health"][0]["id"]
    started = client.post("/api/onboarding/start", json={"preview_id": first["preview_id"],
        "selected": {"health": sport_id}, "skipped": ["education", "profession", "languages", "finance", "personal"]}, headers=headers)
    plan_id = started.json()["created"]["health"]
    second = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    course_id = second["candidates_by_sphere"]["education"][0]["id"]
    result = client.post("/api/onboarding/start", json={"preview_id": second["preview_id"],
        "selected": {"education": course_id}, "skipped": ["health", "profession", "languages", "finance", "personal"]}, headers=headers)
    assert result.status_code == 200
    assert client.get("/api/health/sport/plan").json()["plan"]["id"] == plan_id


def test_simultaneous_start_returns_one_plan_set(client, mailbox):
    from concurrent.futures import ThreadPoolExecutor

    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "concurrent@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    payload = {"preview_id": shown["preview_id"], "selected": {"health": shown["candidates_by_sphere"]["health"][0]["id"]},
               "skipped": ["education", "profession", "languages", "finance", "personal"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post, "/api/onboarding/start", json=payload, headers=headers) for _ in range(2)]
        responses = [future.result() for future in futures]
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()


def test_skipped_finance_does_not_change_currency(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "finance-skip@example.com")
    headers = {"X-CSRF-Token": csrf}
    survey = answers()
    survey["finance"]["currency"] = "USD"
    shown = client.post("/api/onboarding/preview", json=survey, headers=headers).json()
    response = client.post("/api/onboarding/start", json={"preview_id": shown["preview_id"],
        "selected": {}, "skipped": ["health", "education", "profession", "languages", "finance", "personal"]}, headers=headers)
    assert response.status_code == 200, response.text
    with client.app.state.sessionmaker() as db:
        assert db.scalar(select(User).where(User.email == "finance-skip@example.com")).finance_currency == "KZT"


def test_switching_education_course_archives_old_route(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "switch-course@example.com")
    headers = {"X-CSRF-Token": csrf}
    for course in ("java", "go"):
        survey = answers()
        survey["education"]["track"] = course
        shown = client.post("/api/onboarding/preview", json=survey, headers=headers).json()
        response = client.post("/api/onboarding/start", json={"preview_id": shown["preview_id"],
            "selected": {"education": course}, "skipped": ["health", "profession", "languages", "finance", "personal"],
            "confirm_replace": course == "go"}, headers=headers)
        assert response.status_code == 200, response.text
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == "switch-course@example.com"))
        active = db.scalars(select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.active_slot.is_not(None))).all()
        assert [plan.course_id for plan in active] == ["go"]


def test_archive_lists_only_owned_recent_plans(client, mailbox):
    client.app.state.settings = replace(client.app.state.settings, shared_matching_enabled=True)
    csrf = sign_in(client, mailbox, "archive-list@example.com")
    headers = {"X-CSRF-Token": csrf}
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    first_id = shown["candidates_by_sphere"]["health"][0]["id"]
    first = client.post("/api/onboarding/start", json={"preview_id": shown["preview_id"], "selected": {"health": first_id},
        "skipped": ["education", "profession", "languages", "finance", "personal"]}, headers=headers)
    assert first.status_code == 200
    shown = client.post("/api/onboarding/preview", json=answers(), headers=headers).json()
    second_id = next(item["id"] for item in shown["candidates_by_sphere"]["health"] if item["id"] != first_id)
    second = client.post("/api/onboarding/start", json={"preview_id": shown["preview_id"], "selected": {"health": second_id},
        "skipped": ["education", "profession", "languages", "finance", "personal"], "confirm_replace": True}, headers=headers)
    assert second.status_code == 200
    listed = client.get("/api/onboarding/archive")
    assert listed.status_code == 200
    assert [item["plan_id"] for item in listed.json()["items"]] == [first.json()["created"]["health"]]
