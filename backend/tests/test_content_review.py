from datetime import date

from app.content_review import load_reviews, reviewed_variant, variant_digest
from app.nutrition import load_recipes
from app.sport import load_sport_catalog


def test_recipe_requires_explicit_reviewed_allergens() -> None:
    recipe = {
        "id": "simple", "name": "Простое блюдо", "allergens": [],
        "review": {"license": "platform-original", "source": "platform", "checked_at": "2026-10-12", "checked_by": "structural-audit", "recheck_by": "2027-04-12", "allergens_checked": True},
    }
    assert reviewed_variant("recipe", recipe, date(2026, 10, 12))
    assert not reviewed_variant("recipe", {**recipe, "allergens": None}, date(2026, 10, 12))
    assert not reviewed_variant("recipe", {**recipe, "review": {**recipe["review"], "allergens_checked": False}}, date(2026, 10, 12))
    assert not reviewed_variant("recipe", recipe, date(2027, 4, 13))


def test_sport_requires_safety_review_and_digest_includes_exercise() -> None:
    program = {"id": "strength", "title": "Сила", "place": "home", "limitations_supported": False,
               "review": {"license": "platform-original", "source": "platform", "checked_at": "2026-10-12", "checked_by": "structural-audit", "recheck_by": "2027-04-12", "safety_checked": True}}
    assert reviewed_variant("sport", program, date(2026, 10, 12))
    assert not reviewed_variant("sport", {**program, "limitations_supported": None}, date(2026, 10, 12))
    first = variant_digest("sport", program, {"squat": {"name": "Присед"}})
    second = variant_digest("sport", program, {"squat": {"name": "Присед с паузой"}})
    assert first != second


def test_current_catalog_items_carry_reviewed_matching_metadata() -> None:
    for recipe in load_recipes()["recipes"]:
        assert reviewed_variant("recipe", recipe, date(2026, 10, 12)), recipe["id"]
    for program in load_sport_catalog()["programs"]:
        assert reviewed_variant("sport", program, date(2026, 10, 12)), program["id"]


def test_missing_ingredient_allergens_excludes_only_affected_recipes(monkeypatch) -> None:
    from copy import deepcopy
    import app.nutrition as nutrition

    original = nutrition._read_json
    catalog = deepcopy(original("recipes.json"))
    foods = deepcopy(original("foods.json"))
    affected_food = catalog["recipes"][0]["ingredients"][0]["food_id"]
    foods["foods"][affected_food].pop("allergens")
    monkeypatch.setattr(nutrition, "_read_json", lambda name: foods if name == "foods.json" else catalog if name == "recipes.json" else original(name))
    nutrition.load_recipes.cache_clear()
    try:
        loaded = nutrition.load_recipes()
        assert loaded["recipes"]
        assert all(affected_food not in {part["food_id"] for part in recipe["ingredients"]} for recipe in loaded["recipes"])
    finally:
        nutrition.load_recipes.cache_clear()


def test_study_books_and_guides_have_review_records() -> None:
    from importlib.resources import files
    import json

    reviews = load_reviews()
    content = files("app.content")
    courses = json.loads(content.joinpath("study-v1.json").read_text())
    courses += [json.loads(content.joinpath(name).read_text()) for name in ("study-go-v1.json", "study-backend-v2.json")]
    for course in courses:
        assert reviewed_variant("study", {**course, "review": reviews["study"][f"{course['id']}:{course['version']}"]["review"]}, date(2026, 10, 14))
    for kind, name in (("book", "book_suggestions.json"), ("guide", "guides.json")):
        for item in json.loads(content.joinpath(name).read_text()):
            assert reviewed_variant(kind, {**item, "review": reviews[kind][item["id"]]["review"]}, date(2026, 10, 14))
