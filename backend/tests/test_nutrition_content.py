from fastapi.testclient import TestClient

from app.nutrition import NutritionAnswers, NutritionPreferences, compatible_recipes, estimate_nutrition, load_recipes, recipe_nutrition
from conftest import Mailbox
from test_spheres import sign_in


def answers(**overrides):
    values = {"age": 30, "height_cm": 180, "weight_kg": 80, "formula_sex": "male", "activity": "light", "goal": "fat_loss", "pregnant": False, "breastfeeding": False, "special_condition": False}
    values.update(overrides)
    return NutritionAnswers(**values)


def test_estimate_uses_documented_inputs_and_states_limits() -> None:
    estimate = estimate_nutrition(answers())
    assert estimate["estimate"]["resting_kcal"] == 1780
    assert estimate["estimate"]["maintenance_kcal"] == 2723
    assert estimate["estimate"]["target_kcal"] == 2451
    assert estimate["estimate"]["protein_g"] == 112
    assert estimate["estimate"]["carbs_g"] > 0
    assert "pubmed.ncbi.nlm.nih.gov/2305711" in estimate["sources"]["formula"]
    assert estimate_nutrition(answers(age=17))["estimate"] is None
    assert estimate_nutrition(answers(age=79))["estimate"] is None
    assert estimate_nutrition(answers(pregnant=True))["estimate"] is None
    assert estimate_nutrition(answers(breastfeeding=True))["estimate"] is None
    assert estimate_nutrition(answers(special_condition=True))["estimate"] is None
    assert estimate_nutrition(answers(formula_sex="unspecified"))["estimate"] is None
    assert estimate_nutrition(answers(weight_kg=35, height_cm=140, formula_sex="female", age=70))["estimate"] is None
    assert estimate_nutrition(answers(formula_sex="female", goal="maintain"))["estimate"]["resting_kcal"] == 1614


def test_recipe_library_has_real_inputs_and_portion_arithmetic() -> None:
    library = load_recipes()
    assert len(library["recipes"]) >= 53
    assert {recipe["meal"] for recipe in library["recipes"]} == {"breakfast", "lunch", "dinner"}
    assert library["foods"]["oats"]["fdc_id"] == 173904
    assert library["foods"]["oats"]["kcal"] == 379
    assert library["foods"]["chicken_breast"]["protein_g"] == 22.5
    beans = library["foods"]["canned_kidney_beans"]
    assert (beans["kcal"], beans["protein_g"], beans["fat_g"], beans["carbs_g"]) == (121.0, 8.12, 0.93, 20.8)
    assert "ars.usda.gov" in beans["source_url"]
    assert {"buckwheat", "zucchini", "chickpeas", "salmon"}.issubset(library["foods"])
    assert {"salmon_buckwheat_zucchini", "chickpea_tomato_salad", "zucchini_chicken_boats"}.issubset({item["id"] for item in library["recipes"]})
    for food in library["foods"].values():
        assert food["fdc_id"] > 0
        assert food["source_url"].startswith(("https://fdc.nal.usda.gov/food-details/", "https://www.ars.usda.gov/"))
        assert food["source_release"] in {"SR Legacy 2018-04", "SR28 2015"}
        assert food["state"] in {"raw", "dry", "as_packaged"}
        assert all(food[key] >= 0 for key in ("kcal", "protein_g", "fat_g", "carbs_g"))
    for recipe in library["recipes"]:
        assert len(recipe["steps"]) >= 3 and recipe["minutes"] > 0 and recipe["servings"] > 0
        assert recipe["nutrition_per_serving"]["kcal"] > 0
        for item in recipe["ingredients"]:
            assert item["grams"] > 0
            assert item["state"] == library["foods"][item["food_id"]]["state"]
    recipe = library["recipes"][0]
    one = recipe_nutrition(recipe, 1)
    two = recipe_nutrition(recipe, 2)
    assert two["kcal"] == round(one["kcal"] * 2, 1)
    assert two["protein_g"] == round(one["protein_g"] * 2, 1)


def test_added_recipe_sources_have_measured_ingredients_and_preparation() -> None:
    recipes = {item["id"]: item for item in load_recipes()["recipes"]}
    for recipe_id, source in (("baked_chopped_chicken_patties", "menunedeli.ru"), ("oat_pancake_yogurt_banana", "lina.bz")):
        recipe = recipes[recipe_id]
        assert source in recipe["source_url"]
        assert recipe["servings"] > 0
        assert len(recipe["steps"]) >= 3
        assert all(item["grams"] > 0 for item in recipe["ingredients"])
        assert recipe["nutrition_per_serving"]["kcal"] > 0


def test_short_meals_and_allergen_aware_breakfast_have_complete_recipes() -> None:
    quick = compatible_recipes(NutritionPreferences(max_minutes=30))
    assert len(quick["lunch"]) >= 2
    gluten_free = compatible_recipes(NutritionPreferences(allergies=["gluten"], max_minutes=30))
    assert gluten_free["breakfast"]
    restricted = compatible_recipes(NutritionPreferences(allergies=["gluten", "milk", "egg"], max_minutes=30, vegetarian=True, budget="low"))
    assert restricted["breakfast"] and restricted["lunch"]
    for recipe in restricted["breakfast"] + restricted["lunch"]:
        assert recipe["steps"] and recipe["nutrition_per_serving"]["kcal"] > 0
    fish_free = compatible_recipes(NutritionPreferences(allergies=["fish"]))
    assert all("fish" not in recipe["allergens"] for meals in fish_free.values() for recipe in meals)


def test_every_survey_recipe_preference_has_ready_meals_even_at_five_minutes() -> None:
    from itertools import combinations

    allergens = ("gluten", "milk", "egg", "fish")
    for vegetarian in (False, True):
        for count in range(len(allergens) + 1):
            for excluded in combinations(allergens, count):
                meals = compatible_recipes(NutritionPreferences(vegetarian=vegetarian, allergies=list(excluded), max_minutes=5))
                assert all(meals[meal] for meal in ("breakfast", "lunch", "dinner")), (vegetarian, excluded)
                assert all(not set(recipe["allergens"]) & set(excluded) for recipes in meals.values() for recipe in recipes)


def test_strict_quick_vegetarian_preferences_have_real_choices() -> None:
    meals = compatible_recipes(NutritionPreferences(vegetarian=True, allergies=["gluten", "milk", "egg", "fish"], max_minutes=15))
    assert all(len(meals[meal]) >= 3 for meal in ("breakfast", "lunch", "dinner"))
    for meal in ("breakfast", "lunch", "dinner"):
        legumes = {ingredient["food_id"] for recipe in meals[meal] for ingredient in recipe["ingredients"]
                   if ingredient["food_id"] in {"canned_chickpeas", "canned_kidney_beans"}}
        assert legumes == {"canned_chickpeas", "canned_kidney_beans"}


def test_recipes_and_estimate_routes_require_account(client: TestClient, mailbox: Mailbox) -> None:
    assert client.get("/api/health/nutrition/recipes").status_code == 401
    sign_in(client, mailbox, "food@example.com")
    recipes = client.get("/api/health/nutrition/recipes")
    assert recipes.status_code == 200
    assert len(recipes.json()["recipes"]) >= 25
    response = client.post("/api/health/nutrition/estimate", json=answers().model_dump())
    assert response.status_code == 200
    assert response.json()["estimate"]["target_kcal"] == 2451
