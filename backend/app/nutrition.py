import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from app.content_review import reviewed_variant


FORMULA_SOURCE = "https://pubmed.ncbi.nlm.nih.gov/2305711/"
ACTIVITY_SOURCE = "https://www.fao.org/4/y5686e/y5686e07.htm"
PROTEIN_SOURCE = "https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0177-8"
LOW_INTAKE_SOURCE = "https://www.niddk.nih.gov/bwp"
ACTIVITY_FACTORS = {"light": 1.53, "moderate": 1.76, "vigorous": 2.25}


class NutritionAnswers(BaseModel):
    age: int = Field(ge=1, le=120)
    height_cm: float = Field(ge=100, le=230)
    weight_kg: float = Field(ge=25, le=350)
    formula_sex: Literal["male", "female", "unspecified"]
    activity: Literal["light", "moderate", "vigorous"]
    goal: Literal["fat_loss", "maintain", "gain"]
    pregnant: bool = False
    breastfeeding: bool = False
    special_condition: bool = False


def estimate_nutrition(answers: NutritionAnswers) -> dict[str, Any]:
    sources = {"formula": FORMULA_SOURCE, "activity": ACTIVITY_SOURCE, "protein": PROTEIN_SOURCE, "low_intake": LOW_INTAKE_SOURCE}
    reasons: list[str] = []
    if not 19 <= answers.age <= 78:
        reasons.append("Опубликованная формула проверялась для взрослых 19–78 лет; для этого возраста расчёт не выдаётся.")
    if answers.formula_sex == "unspecified":
        reasons.append("Для этой формулы нужен один из двух исходных параметров пола; без него расчёт не выдаётся.")
    if answers.pregnant or answers.breastfeeding:
        reasons.append("При беременности или грудном вскармливании обычный расчёт не применяется.")
    if answers.special_condition:
        reasons.append("При указанном особом состоянии готовый расчёт не применяется.")
    if reasons:
        return {"estimate": None, "reasons": reasons, "sources": sources}
    resting = 10 * answers.weight_kg + 6.25 * answers.height_cm - 5 * answers.age + (5 if answers.formula_sex == "male" else -161)
    maintenance = resting * ACTIVITY_FACTORS[answers.activity]
    adjustment = {"fat_loss": 0.9, "maintain": 1.0, "gain": 1.1}[answers.goal]
    target = maintenance * adjustment
    if target < 1200:
        return {"estimate": None, "reasons": ["Расчёт даёт очень низкую калорийность; готовая цель не выдаётся. Для индивидуального плана обратитесь к специалисту."], "sources": sources}
    # A planning split, not an individual prescription; protein assumes regular resistance exercise.
    protein = round(answers.weight_kg * (1.4 if answers.goal == "fat_loss" else 1.0))
    fat = round(target * 0.30 / 9)
    carbs = round((target - protein * 4 - fat * 9) / 4)
    if carbs < 0:
        return {"estimate": None, "reasons": ["Для этих параметров не получается безопасно разложить ориентир по БЖУ."], "sources": sources}
    result = {
        "resting_kcal": round(resting), "maintenance_kcal": round(maintenance), "target_kcal": round(target),
        "protein_g": protein, "fat_g": fat, "carbs_g": carbs, "activity_factor": ACTIVITY_FACTORS[answers.activity],
        "explanation": "Mifflin–St Jeor оценивает расход в покое по массе, росту, возрасту и параметру пола. Уровень активности умножает оценку на PAL. Цель похудения здесь — условные 10% ниже поддержания, набора — 10% выше; жиры — 30% энергии, углеводы — остаток. Белок при похудении и силовых занятиях — 1,4 г/кг. Это ориентир, а не медицинское назначение; сравнивайте с динамикой веса и самочувствием.",
        "limits": "Формула отражает средние данные и не учитывает состав тела, лекарства и особенности здоровья. Рецепты используют состав исходных продуктов: потери при приготовлении не вычисляются.",
    }
    return {"estimate": result, "reasons": [], "sources": sources}


def _read_json(name: str) -> dict[str, Any]:
    return json.loads(files("app.content").joinpath(name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_recipes() -> dict[str, Any]:
    food_file = _read_json("foods.json")
    recipe_file = _read_json("recipes.json")
    review_file = _read_json("content_review.json")
    foods = food_file["foods"]
    recipes = recipe_file["recipes"]
    if len({item["id"] for item in recipes}) != len(recipes):
        raise ValueError("Повторяются идентификаторы рецептов")
    for food in foods.values():
        if food.get("state") not in {"raw", "dry", "as_packaged"} or food.get("source_release") not in {"SR Legacy 2018-04", "SR28 2015"}:
            raise ValueError("Неверное состояние или источник продукта")
        expected_fdc = f"https://fdc.nal.usda.gov/food-details/{food.get('fdc_id')}/nutrients"
        official_sr28 = "https://www.ars.usda.gov/ARSUserFiles/80400535/Data/SR/SR28/reports/sr28fg16.pdf"
        if food.get("source_url") != expected_fdc and not (food.get("source_release") == "SR28 2015" and food.get("source_url") == official_sr28):
            raise ValueError("Неверная ссылка на пищевую ценность")
        if any(food.get(field, -1) < 0 for field in ("kcal", "protein_g", "fat_g", "carbs_g")):
            raise ValueError("Неполные данные продукта")
    eligible_recipes = []
    for recipe in recipes:
        if not recipe.get("steps") or recipe["minutes"] < 1 or recipe["servings"] < 1 or recipe["meal"] not in ("breakfast", "lunch", "dinner"):
            raise ValueError("Неполный рецепт")
        if recipe["cost_tier"] not in ("low", "medium"):
            raise ValueError("Неизвестная доступность рецепта")
        totals = {field: 0.0 for field in ("kcal", "protein_g", "fat_g", "carbs_g")}
        allergens: set[str] = set()
        allergens_known = True
        for item in recipe["ingredients"]:
            food = foods.get(item["food_id"])
            if food is None or item["state"] != food["state"] or item["grams"] <= 0:
                raise ValueError("Неверный ингредиент или состояние до приготовления")
            if not isinstance(food.get("allergens"), list):
                allergens_known = False
                break
            allergens.update(food["allergens"])
            for field in totals:
                totals[field] += food[field] * item["grams"] / 100
        if not allergens_known:
            continue
        recipe["allergens"] = sorted(allergens)
        reviewed = review_file["recipes"].get(recipe["id"])
        if reviewed and reviewed.get("allergens") == recipe["allergens"]:
            recipe["review"] = reviewed["review"]
        recipe["nutrition_per_serving"] = {field: round(value / recipe["servings"], 1) for field, value in totals.items()}
        eligible_recipes.append(recipe)
    return {"version": recipe_file["version"], "basis": food_file["basis"], "foods": foods, "recipes": eligible_recipes}


def recipe_nutrition(recipe: dict[str, Any], portions: float) -> dict[str, float]:
    if not 0 < portions <= 4:
        raise ValueError("Количество порций должно быть больше нуля и не больше четырёх")
    return {field: round(value * portions, 1) for field, value in recipe["nutrition_per_serving"].items()}


class NutritionPreferences(BaseModel):
    vegetarian: bool = False
    allergies: list[Literal["gluten", "milk", "egg", "fish"]] = Field(default_factory=list)
    excluded_food_ids: list[str] = Field(default_factory=list, max_length=30)
    budget: Literal["low", "any"] = "any"
    max_minutes: int = Field(default=45, ge=5, le=180)


def compatible_recipes(preferences: NutritionPreferences) -> dict[str, list[dict[str, Any]]]:
    library = load_recipes()
    unknown = set(preferences.excluded_food_ids) - set(library["foods"])
    if unknown:
        raise ValueError("Неизвестный исключённый продукт")
    chosen: dict[str, list[dict[str, Any]]] = {meal: [] for meal in ("breakfast", "lunch", "dinner")}
    today = datetime.now(ZoneInfo("Asia/Almaty")).date()
    for recipe in library["recipes"]:
        if not reviewed_variant("recipe", recipe, today):
            continue
        if preferences.vegetarian and not recipe["vegetarian"]:
            continue
        if set(preferences.allergies) & set(recipe["allergens"]):
            continue
        if set(preferences.excluded_food_ids) & {item["food_id"] for item in recipe["ingredients"]}:
            continue
        if preferences.budget == "low" and recipe["cost_tier"] != "low":
            continue
        if recipe["minutes"] > preferences.max_minutes:
            continue
        chosen[recipe["meal"]].append(recipe)
    return chosen


def snapshot_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    saved = deepcopy(recipe)
    foods = load_recipes()["foods"]
    for item in saved["ingredients"]:
        food = foods[item["food_id"]]
        item["food_name"] = food["name"]
        item["source_url"] = food["source_url"]
    return saved


def create_menu_days(start_date: date, preferences: NutritionPreferences, target_kcal: int, excluded_recipe_ids: set[str] | None = None) -> list[dict[str, Any]]:
    compatible = compatible_recipes(preferences)
    if excluded_recipe_ids:
        compatible = {meal: [recipe for recipe in recipes if recipe["id"] not in excluded_recipe_ids]
                      for meal, recipes in compatible.items()}
    missing = [meal for meal, recipes in compatible.items() if not recipes]
    if missing:
        raise ValueError("Недостаточно подходящих рецептов для: " + ", ".join(missing))
    days = []
    for offset in range(7):
        picked = [compatible[meal][offset % len(compatible[meal])] for meal in ("breakfast", "lunch", "dinner")]
        base_kcal = sum(recipe["nutrition_per_serving"]["kcal"] for recipe in picked)
        portions = round(target_kcal / base_kcal * 4) / 4
        if not 0.5 <= portions <= 4:
            raise ValueError("Для выбранных условий не получается составить разумный размер порций.")
        days.append({"date": (start_date + timedelta(days=offset)).isoformat(), "meals": [
            {"meal": recipe["meal"], "recipe_id": recipe["id"], "portions": portions, "recipe": snapshot_recipe(recipe)} for recipe in picked
        ]})
    return days


def summarize_menu(days: list[dict[str, Any]], target_kcal: int) -> dict[str, Any]:
    totals_by_day = []
    groceries: dict[tuple[str, str], dict[str, Any]] = {}
    for day in days:
        total = {field: 0.0 for field in ("kcal", "protein_g", "fat_g", "carbs_g")}
        meals = []
        for entry in day["meals"]:
            recipe = entry["recipe"]
            nutrition = recipe_nutrition(recipe, entry["portions"])
            meals.append({"meal": entry["meal"], "recipe_id": entry["recipe_id"], "recipe": recipe,
                          "portions": entry["portions"], "nutrition": nutrition})
            for field, value in nutrition.items():
                total[field] += value
            for ingredient in recipe["ingredients"]:
                key = ingredient["food_id"], ingredient["state"]
                item = groceries.setdefault(key, {"food_id": key[0], "name": ingredient["food_name"], "state": key[1], "unit": "g", "quantity": 0.0})
                item["quantity"] += ingredient["grams"] * entry["portions"] / recipe["servings"]
        rounded = {field: round(value, 1) for field, value in total.items()}
        totals_by_day.append({"date": day["date"], "meals": meals, "total": rounded, "difference_kcal": round(rounded["kcal"] - target_kcal, 1)})
    shopping = [{**item, "quantity": round(item["quantity"], 1)} for item in sorted(groceries.values(), key=lambda item: (item["name"], item["state"]))]
    return {"days": totals_by_day, "shopping_list": shopping}
