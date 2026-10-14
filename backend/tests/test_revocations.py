from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.content_admin import change_revocation
from app.content_review import is_revoked, revocation_reason
from app.db import Base
from app.models import ContentRevocationEvent
from test_spheres import sign_in
from test_sport import plan_answers
from test_nutrition import nutrition_profile, today
from app.nutrition import load_recipes


def test_revoke_restore_audit_and_reason(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'revocations.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert not is_revoked(db, "sport", "strength", "v1")
        change_revocation(db, "revoke", "sport", "strength", "v1", "Unsafe exercise", "operator")
        db.commit()
        assert is_revoked(db, "sport", "strength", "v1")
        assert revocation_reason(db, "sport", "strength", "v1") == "Unsafe exercise"
        change_revocation(db, "restore", "sport", "strength", "v1", "Fixed exercise", "reviewer")
        db.commit()
        assert not is_revoked(db, "sport", "strength", "v1")
        events = db.scalars(select(ContentRevocationEvent).order_by(ContentRevocationEvent.created_at)).all()
        assert [(event.action, event.actor, event.reason) for event in events] == [
            ("revoke", "operator", "Unsafe exercise"), ("restore", "reviewer", "Fixed exercise")
        ]
        assert all(event.created_at for event in events)
        try:
            change_revocation(db, "revoke", "sport", "strength", "v1", " ", "operator")
        except ValueError:
            pass
        else:
            raise AssertionError("blank reason accepted")


def test_revoked_active_sport_plan_warns_and_new_assignment_fails(client, mailbox):
    csrf = sign_in(client, mailbox, "revoked@example.com")
    headers = {"X-CSRF-Token": csrf}
    saved = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers).json()["plan"]
    with client.app.state.sessionmaker() as db:
        change_revocation(db, "revoke", "sport", saved["program"]["id"], saved["content_version"], "Review pending", "operator")
        db.commit()
    current = client.get("/api/health/sport/plan").json()["plan"]
    assert current["id"] == saved["id"]
    assert current["revoked"] is True
    assert current["revocation_reason"] == "Review pending"
    alternative = client.post("/api/health/sport/match", json=plan_answers()).json()["program"]
    assert alternative is None or alternative["id"] != saved["program"]["id"]
    replacement = client.put("/api/health/sport/plan", json={"answers": plan_answers()}, headers=headers)
    assert replacement.status_code == 200
    assert replacement.json()["proposed"]["id"] != saved["program"]["id"]


def test_revoked_recipe_warns_on_menu_and_cannot_be_reassigned(client, mailbox):
    csrf = sign_in(client, mailbox, "menu-revoked@example.com")
    headers = {"X-CSRF-Token": csrf}
    assert client.put("/api/health/nutrition/profile", json=nutrition_profile(), headers=headers).status_code == 200
    saved = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers).json()["menu"]
    recipe_id = saved["days"][0]["meals"][0]["recipe_id"]
    with client.app.state.sessionmaker() as db:
        change_revocation(db, "revoke", "recipe", recipe_id, load_recipes()["version"], "Allergen data correction", "operator")
        db.commit()
    current = client.get("/api/health/nutrition/menu").json()["menu"]
    assert current["id"] == saved["id"]
    assert current["revoked"] is True
    assert recipe_id in current["revoked_recipe_ids"]
    assert current["revocation_reasons"][recipe_id] == "Allergen data correction"
    proposed = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers)
    assert proposed.status_code == 200
    assert recipe_id not in {meal["recipe_id"] for day in proposed.json()["proposed"]["days"] for meal in day["meals"]}
    assert client.post("/api/health/nutrition/food-log", json={"date": today(), "recipe_id": recipe_id, "portions": 1,
                                                         "create_key": "revoked"}, headers=headers).status_code == 422
