from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from conftest import Mailbox
from test_spheres import sign_in


def nutrition_profile(**preference_changes):
    preferences = {"vegetarian": False, "allergies": [], "excluded_food_ids": [], "budget": "any", "max_minutes": 45}
    preferences.update(preference_changes)
    return {"answers": {"age": 30, "height_cm": 180, "weight_kg": 80, "formula_sex": "male", "activity": "light", "goal": "fat_loss", "pregnant": False, "breastfeeding": False, "special_condition": False}, "preferences": preferences}


def today():
    return datetime.now(ZoneInfo("Asia/Almaty")).date().isoformat()


def test_profile_and_menu_are_private_complete_and_diet_compatible(client: TestClient, mailbox: Mailbox) -> None:
    assert client.get("/api/health/nutrition/profile").status_code == 401
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    assert client.put("/api/health/nutrition/profile", json=nutrition_profile(), headers=headers).status_code == 200
    profile = client.get("/api/health/nutrition/profile").json()["profile"]
    assert profile["estimate"]["target_kcal"] == 2451
    created = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers)
    assert created.status_code == 200
    assert created.json()["status"] == "saved"
    menu = created.json()["menu"]
    assert len(menu["days"]) == 7
    assert all(len(day["meals"]) == 3 for day in menu["days"])
    assert {meal["meal"] for meal in menu["days"][0]["meals"]} == {"breakfast", "lunch", "dinner"}
    assert menu["shopping_list"] and all(item["unit"] == "g" for item in menu["shopping_list"])
    assert menu["days"][0]["total"]["kcal"] > 0
    assert client.get("/api/health/nutrition/menu").json()["menu"]["id"] == menu["id"]
    sign_in(client, mailbox, "two@example.com")
    assert client.get("/api/health/nutrition/profile").json()["profile"] is None
    assert client.get("/api/health/nutrition/menu").json()["menu"] is None


def test_menu_portions_substitution_and_history_snapshots(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    client.put("/api/health/nutrition/profile", json=nutrition_profile(), headers=headers)
    first = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers).json()["menu"]
    breakfast = next(item for item in first["days"][0]["meals"] if item["meal"] == "breakfast")
    original_kcal = first["days"][0]["total"]["kcal"]
    food_payload = {"date": today(), "recipe_id": breakfast["recipe_id"], "portions": 1, "create_key": "breakfast-1"}
    logged = client.post("/api/health/nutrition/food-log", json=food_payload, headers=headers)
    assert logged.status_code == 201
    assert client.post("/api/health/nutrition/food-log", json=food_payload, headers=headers).json()["id"] == logged.json()["id"]
    assert client.post("/api/health/nutrition/food-log", json={**food_payload, "portions": 2}, headers=headers).status_code == 409
    changed = client.patch("/api/health/nutrition/menu", json={"date": today(), "meal": "breakfast", "recipe_id": breakfast["recipe_id"], "portions": 2}, headers=headers)
    assert changed.status_code == 200
    assert changed.json()["menu"]["id"] != first["id"]
    assert changed.json()["menu"]["days"][0]["total"]["kcal"] > original_kcal
    assert changed.json()["menu"]["shopping_list"] != first["shopping_list"]
    alternative = next(item["id"] for item in client.get("/api/health/nutrition/recipes").json()["recipes"] if item["meal"] == "breakfast" and item["id"] != breakfast["recipe_id"])
    swapped = client.patch("/api/health/nutrition/menu", json={"date": today(), "meal": "breakfast", "recipe_id": alternative, "portions": 1}, headers=headers)
    assert swapped.status_code == 200
    assert next(item for item in swapped.json()["menu"]["days"][0]["meals"] if item["meal"] == "breakfast")["recipe_id"] == alternative
    assert client.get("/api/health/nutrition/food-log").json()["items"][0]["nutrition"] == logged.json()["nutrition"]
    preview = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers)
    assert preview.json()["status"] == "preview"
    assert client.get("/api/health/nutrition/menu").json()["menu"]["id"] == swapped.json()["menu"]["id"]
    other_csrf = sign_in(client, mailbox, "two@example.com")
    assert client.get("/api/health/nutrition/food-log").json()["items"] == []
    assert client.patch("/api/health/nutrition/menu", json={"date": today(), "meal": "breakfast", "recipe_id": alternative, "portions": 1}, headers={"X-CSRF-Token": other_csrf}).status_code == 404


def test_menu_no_match_weight_log_and_invalid_inputs(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    client.put("/api/health/nutrition/profile", json=nutrition_profile(vegetarian=True, allergies=["gluten", "milk", "egg"], excluded_food_ids=["rice", "canned_chickpeas", "canned_kidney_beans"], budget="low"), headers=headers)
    no_match = client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers)
    assert no_match.status_code == 422
    assert client.get("/api/health/nutrition/menu").json()["menu"] is None
    client.put("/api/health/nutrition/profile", json=nutrition_profile(), headers=headers)
    weight = client.post("/api/health/nutrition/weight-log", json={"date": today(), "weight_kg": 80}, headers=headers)
    assert weight.status_code == 201
    assert client.post("/api/health/nutrition/weight-log", json={"date": today(), "weight_kg": 80}, headers=headers).json()["id"] == weight.json()["id"]
    assert client.post("/api/health/nutrition/weight-log", json={"date": today(), "weight_kg": 81}, headers=headers).status_code == 409
    assert len(client.get("/api/health/nutrition/weight-log").json()["items"]) == 1
    assert client.post("/api/health/nutrition/food-log", json={"date": today(), "recipe_id": "missing", "portions": 1, "create_key": "bad"}, headers=headers).status_code == 422
    client.post("/api/health/nutrition/menu", json={"start_date": today()}, headers=headers)
    client.put("/api/health/nutrition/profile", json=nutrition_profile(vegetarian=True), headers=headers)
    assert client.get("/api/health/nutrition/menu").json()["menu"]["stale"] is True
    assert client.patch("/api/health/nutrition/menu", json={"date": today(), "meal": "lunch", "recipe_id": "lentil_rice_tomato", "portions": 1}, headers=headers).status_code == 409
