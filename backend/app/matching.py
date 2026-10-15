"""Deterministic catalog choices for the six-sphere survey."""

import json
from datetime import datetime
from importlib.resources import files
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.content_review import is_revoked, load_reviews, reviewed_variant, variant_digest
from app.nutrition import NutritionPreferences, compatible_recipes, load_recipes
from app.sport import load_sport_catalog, select_program
from app.sport_coverage import audit_coverage
from app.study import course as study_course

if TYPE_CHECKING:
    from app.routes.onboarding import Survey


def _candidate(kind: str, item: dict, version: str, dependencies: dict, reason: str) -> dict:
    return {"kind": kind, "id": item["id"], "version": version, "digest": variant_digest(kind, item, dependencies),
            "title": item.get("title", item.get("name", item["id"])), "reason": reason}


def match_survey(survey: "Survey", timezone: str, db: Session) -> dict:
    # Import here to keep the existing survey model as the single validation boundary.
    from app.routes.onboarding import build_preview, choices, study_match

    areas = build_preview(survey, timezone)["areas"]
    result: dict[str, list[dict]] = {sphere: [] for sphere in areas}
    today = datetime.now(ZoneInfo(timezone)).date()
    book = areas.get("education", {}).get("book")
    if book:
        books = json.loads(files("app.content").joinpath("book_suggestions.json").read_text(encoding="utf-8"))
        item = next((entry for entry in books if entry["title"] == book["title"] and entry["author"] == book["author"]), None)
        review = load_reviews()["book"].get(item["id"], {}).get("review") if item else None
        if not item or not reviewed_variant("book", {**item, "review": review}, today) or is_revoked(db, "book", item["id"], str(item.get("version", "v1"))):
            areas["education"]["book"] = None
    guide_versions = {entry["id"]: str(entry.get("version", "v1")) for entry in json.loads(files("app.content").joinpath("guides.json").read_text(encoding="utf-8"))}
    for sphere, area in areas.items():
        for field in ("guide", "material"):
            material = area.get(field)
            if isinstance(material, dict) and material.get("route"):
                guide_id = material["route"].split("#")[-1]
                if guide_id != material["route"] and is_revoked(db, "guide", guide_id, guide_versions.get(guide_id, "v1")):
                    area[field] = None
        for field in ("sport", "study"):
            section = area.get(field)
            material = section.get("material") if isinstance(section, dict) else None
            if isinstance(material, dict) and material.get("route"):
                guide_id = material["route"].split("#")[-1]
                if guide_id != material["route"] and is_revoked(db, "guide", guide_id, guide_versions.get(guide_id, "v1")):
                    section["material"] = None
    sport = survey.health.sport
    if sport and select_program(sport)["program"]:
        catalog = load_sport_catalog()
        requested_level = {"returning": "beginner", "irregular": "intermediate"}.get(sport.level, sport.level)
        complete_ids = {item["id"] for item in audit_coverage(catalog["programs"], catalog["exercises"])["available_combinations"]}
        for program in catalog["programs"]:
            if program["goal"] != sport.goal or program["place"] != sport.place or program["level"] != requested_level or sport.days_per_week not in program["supported_days"]:
                continue
            if sport.level in ("returning", "irregular", "regular") and program["id"] not in complete_ids:
                continue
            if program["min_minutes"] > sport.minutes_per_session or not set(program["required_equipment"]) <= set(sport.equipment):
                continue
            if not reviewed_variant("sport", program, today) or is_revoked(db, "sport", program["id"], catalog["version"]):
                continue
            exercise_ids = {entry["exercise_id"] for session in program["sessions"] for entry in session["work"]}
            dependencies = {key: catalog["exercises"][key] for key in sorted(exercise_ids)}
            result["health"].append(_candidate("sport", program, catalog["version"], dependencies,
                                               f"{sport.days_per_week} занятия в неделю, {program['min_minutes']} минут, {sport.place}"))
        result["health"].sort(key=lambda c: (-next(p["min_minutes"] for p in catalog["programs"] if p["id"] == c["id"]), c["id"]))
        if not result["health"]:
            areas["health"]["sport"] = {"status": "unavailable", "reason": "Проверенной доступной программы нет."}
        else:
            areas["health"]["sport"] = {"status": "matched", "title": result["health"][0]["title"], "route": "/health/sport"}
    # Recipe recommendations are separately filterable content, never an automatic plan.
    recipes = compatible_recipes(NutritionPreferences(vegetarian=survey.health.vegetarian,
        allergies=survey.health.allergies, max_minutes=survey.health.max_cooking_minutes))
    recipe_catalog = load_recipes()
    recipe_choices = []
    for group in recipes.values():
        for recipe in group:
            if not reviewed_variant("recipe", recipe, today) or is_revoked(db, "recipe", recipe["id"], recipe_catalog["version"]):
                continue
            dependencies = {entry["food_id"]: recipe_catalog["foods"][entry["food_id"]] for entry in recipe["ingredients"]}
            nutrition = recipe["nutrition_per_serving"]
            if survey.health.nutrition_goal == "gain":
                rank = -(nutrition["kcal"] + nutrition["protein_g"] * 4)
                reason = f"Для набора: {nutrition['kcal']} ккал и {nutrition['protein_g']} г белка на порцию"
            elif survey.health.nutrition_goal == "fat_loss":
                rank = -(nutrition["protein_g"] / max(nutrition["kcal"], 1))
                reason = f"Для снижения веса: {nutrition['protein_g']} г белка на {nutrition['kcal']} ккал"
            else:
                rank = 0
                reason = f"{recipe['minutes']} минут на приготовление"
            recipe_choices.append((rank, recipe["id"], _candidate("recipe", recipe, recipe_catalog["version"], dependencies, reason)))
    result["health_recipes"] = [item for _, _, item in sorted(recipe_choices)]
    areas["health"]["recipes"]["count"] = len(recipe_choices)
    areas["health"]["recipes"]["example"] = result["health_recipes"][0]["title"] if recipe_choices else None
    areas["health"]["recipes"]["status"] = "matched" if recipe_choices else "unavailable"
    for sphere, value in zip(("education", "profession", "languages"), choices(survey, timezone)):
        if value is None or study_match(value, "", "")["status"] != "matched":
            continue
        course = study_course(value.course_id, value.version)
        review = load_reviews()["study"].get(f"{course['id']}:{course['version']}", {}).get("review")
        reviewed = {**course, "review": review}
        if reviewed_variant("study", reviewed, today) and not is_revoked(db, "study", course["id"], course["version"]):
            result[sphere].append(_candidate("study", reviewed, course["version"], {}, f"{value.minutes} минут на занятие"))
        else:
            areas[sphere]["study"] = {"status": "unavailable", "reason": "Проверенный курс временно недоступен."}
    return {"areas": areas, "candidates_by_sphere": result,
            "candidate_digests": {sphere: {item["id"]: item["digest"] for item in items} for sphere, items in result.items()}}
