"""Synthetic catalog coverage gate. No account or personal data is read."""

import argparse
import hashlib
import itertools
import json
from datetime import date, datetime, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content_review import load_reviews
from app.db import Base
from app.matching import match_survey
from app.nutrition import load_recipes
from app.routes.onboarding import Survey
from app.sport import load_sport_catalog
from app.study import catalog


def study_help_coverage(help_entries: list[dict] | None = None) -> dict:
    """Compare authored help with every available immutable course version."""
    if help_entries is None:
        path = files("app.content").joinpath("study-help-v1.json")
        help_entries = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    available: set[str] = set()
    courses: dict[str, dict[str, dict[str, int]]] = {}
    for version in ("v1", "v2", "v3"):
        for item in catalog(version):
            course_id = item["id"]
            effective_version = item["version"]
            if effective_version in courses.get(course_id, {}):
                continue
            count = 0
            for lesson in item["lessons"]:
                for index, _question in enumerate(lesson["quiz"]):
                    available.add(f"{course_id}:{effective_version}:{lesson['id']}:{index}")
                    count += 1
            courses.setdefault(course_id, {})[effective_version] = {
                "lessons": len(item["lessons"]), "questions": count, "questions_with_help": 0,
            }
    supplied = {f"{entry['course_id']}:{entry['course_version']}:{entry['lesson_id']}:{entry['question_index']}"
                for entry in help_entries}
    for key in available & supplied:
        course_id, version, _lesson_id, _index = key.split(":")
        courses[course_id][version]["questions_with_help"] += 1
    return {"courses": courses, "missing": sorted(available - supplied), "unreachable": sorted(supplied - available)}


def _survey(goal: str, level: str, place: str, days: int, limitations: bool, route: str, language: str) -> Survey:
    equipment = {"home": ["low_bar", "bench", "dumbbells", "bands", "barbell"],
                 "outdoor": ["low_bar", "bench", "bands"],
                 "gym": ["low_bar", "bench", "machines", "dumbbells", "bands", "barbell"]}[place]
    weekdays = {2: [1, 4], 3: [1, 3, 5], 4: [1, 2, 4, 6]}[days]
    return Survey.model_validate({
        "health": {"sport": {"goal": goal, "level": level, "place": place, "equipment": equipment,
                             "days_per_week": days, "minutes_per_session": 90, "limitations": limitations,
                             "weekdays": weekdays},
                   "vegetarian": False, "allergies": [], "max_cooking_minutes": 90, "nutrition_goal": "maintain"},
        "education": {"track": route, "reading_interest": "Короткие истории", "minutes": 45, "weekdays": [0, 2, 4]},
        "profession": {"track": "java-backend", "minutes": 45, "weekdays": [1, 3]},
        "languages": {"level": language, "goal": "general", "minutes": 45, "weekdays": [0, 2, 4]},
        "finance": {"currency": "KZT", "focus": "record"},
        "personal": {"focus": "journal"},
    })


def build_report() -> dict:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    seen = {kind: set() for kind in ("sport", "recipe", "study")}
    study_pairs: set[tuple[str, str]] = set()
    education_profiles = []
    signatures = []
    with Session(engine) as db:
        dimensions = itertools.product(("fat_loss_muscle_focus", "maintain", "strength_gain"),
            ("beginner", "intermediate"), ("home", "outdoor", "gym"), (2, 3, 4), (False, True))
        for index, values in enumerate(dimensions):
            survey = _survey(*values, ("java", "go", "reading")[index % 3], ("A2", "B1", "B2")[(index // 3) % 3])
            survey.health.vegetarian = index % 2 == 0
            survey.health.allergies = ["milk"] if index % 5 == 0 else []
            survey.health.max_cooking_minutes = (30, 45, 90)[index % 3]
            survey.health.nutrition_goal = ("fat_loss", "maintain", "gain")[index % 3]
            study_pairs.add((survey.education.track, survey.languages.level))
            matched = match_survey(survey, "Asia/Almaty", db)
            signature = {}
            for sphere, choices in matched["candidates_by_sphere"].items():
                signature[sphere] = [item["id"] for item in choices]
                for choice in choices:
                    seen[choice["kind"]].add(choice["id"])
            signature["status"] = {
                "sport": matched["areas"]["health"]["sport"].get("status"),
                "sport_reason": matched["areas"]["health"]["sport"].get("reason"),
                "recipes": matched["areas"]["health"]["recipes"].get("status"),
                "education": matched["areas"]["education"]["study"].get("status"),
                "profession": matched["areas"]["profession"]["study"].get("status"),
                "languages": matched["areas"]["languages"]["study"].get("status"),
            }
            signatures.append(signature)
        for route, language in itertools.product(("java", "go", "reading", "both", "go-reading", "none"),
                                                  ("A2", "B1", "B2")):
            survey = _survey("maintain", "beginner", "home", 2, False, route, language)
            matched = match_survey(survey, "Asia/Almaty", db)
            courses = matched["candidates_by_sphere"]["education"]
            education_profiles.append({"track": route, "language": language,
                                       "course": courses[0]["id"] if courses else None,
                                       "book": bool(matched["areas"]["education"].get("book"))})
    sport = {item["id"] for item in load_sport_catalog()["programs"]}
    recipe = {item["id"] for item in load_recipes()["recipes"]}
    study = {"java", "go", "java-backend", "english"}
    catalog = {"sport": sport, "recipe": recipe, "study": study}
    due = []
    reviews = load_reviews()
    for kind, key in (("sport", "sport"), ("recipe", "recipes"), ("study", "study"), ("book", "book"), ("guide", "guide")):
        for item_id, record in reviews[key].items():
            review = record.get("review", {})
            try:
                if date.fromisoformat(review["recheck_by"]) <= datetime.now(ZoneInfo("Asia/Almaty")).date() + timedelta(days=30):
                    due.append(f"{kind}:{item_id}")
            except (KeyError, ValueError):
                due.append(f"{kind}:{item_id}")
    canonical = json.dumps(signatures, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"profiles": len(signatures), "study_pairs": [list(pair) for pair in sorted(study_pairs)],
            "education_profiles": education_profiles,
            "unreachable": {kind: sorted(ids - seen[kind]) for kind, ids in catalog.items()},
            "due_soon": sorted(due), "signature": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "study_help": study_help_coverage()}


def compare_baseline(report: dict) -> bool:
    baseline = json.loads(files("app.content").joinpath("coverage_baseline.json").read_text(encoding="utf-8"))
    return baseline == report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.update:
        files("app.content").joinpath("coverage_baseline.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and not compare_baseline(report):
        raise SystemExit("Catalog coverage changed; review and update the baseline intentionally")


if __name__ == "__main__":
    main()
