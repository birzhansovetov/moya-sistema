import json
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator
from app.content_review import reviewed_variant


class SportAnswers(BaseModel):
    goal: Literal["fat_loss_muscle_focus", "maintain", "strength_gain"]
    level: Literal["beginner", "intermediate"]
    place: Literal["home", "outdoor", "gym"]
    equipment: list[Literal["low_bar", "bench", "machines", "dumbbells", "bands", "barbell"]] = Field(default_factory=list)
    days_per_week: int = Field(ge=1, le=7)
    minutes_per_session: int = Field(ge=10, le=180)
    limitations: bool = False
    weekdays: list[int] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def check_weekdays(self):
        if len(self.weekdays) != self.days_per_week or len(set(self.weekdays)) != len(self.weekdays) or any(day < 1 or day > 7 for day in self.weekdays):
            raise ValueError("Выберите разные дни недели по числу тренировок")
        return self


def _read_json(name: str) -> dict[str, Any]:
    return json.loads(files("app.content").joinpath(name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_sport_catalog() -> dict[str, Any]:
    exercise_file = _read_json("exercises.json")
    program_file = _read_json("sport_programs.json")
    review_file = _read_json("content_review.json")
    exercises = exercise_file["exercises"]
    programs = program_file["programs"]
    if len({item["id"] for item in programs}) != len(programs):
        raise ValueError("Повторяются идентификаторы программ")
    for exercise in exercises.values():
        if not all(exercise.get(field) for field in ("name", "technique", "common_errors", "easier_version", "substitution", "source")):
            raise ValueError("Неполная инструкция упражнения")
        if not exercise["source"].startswith("https://"):
            raise ValueError("Источник упражнения должен быть HTTPS")
        for alternative in exercise.get("alternatives", []):
            if alternative.get("exercise_id") not in exercises or not set(alternative.get("places", [])) <= {"home", "outdoor", "gym"} or not set(alternative.get("required_equipment", [])) <= {"low_bar", "bench", "machines", "dumbbells", "bands", "barbell"}:
                raise ValueError("Неверная замена упражнения")
    for program in programs:
        reviewed = review_file["sport"].get(program["id"])
        if reviewed:
            program["limitations_supported"] = reviewed.get("limitations_supported")
            program["review"] = reviewed.get("review")
        if len(program.get("sessions", [])) < max(program.get("supported_days", [3])) or not program.get("sources"):
            raise ValueError("Неполная спортивная программа")
        for session in program["sessions"]:
            if not session.get("warmup") or not session.get("cooldown") or len(session.get("work", [])) < 4:
                raise ValueError("Неполное занятие")
            for work in session["work"]:
                if work["exercise_id"] not in exercises:
                    raise ValueError("Неизвестное упражнение")
                if work["sets"] < 1 or work["rest_seconds"] < 30 or not work.get("reps"):
                    raise ValueError("Неполная нагрузка упражнения")
    return {"version": program_file["version"], "exercises": exercises, "programs": programs}


def select_program(answers: SportAnswers, excluded_ids: set[str] | None = None) -> dict[str, Any]:
    catalog = load_sport_catalog()
    reasons: list[str] = []
    if answers.limitations:
        reasons.append("При указанных ограничениях проверенной программы пока нет.")
    today = datetime.now(ZoneInfo("Asia/Almaty")).date()
    candidates = [program for program in catalog["programs"] if program["id"] not in (excluded_ids or set())
                  and reviewed_variant("sport", program, today)
                  and program["goal"] == answers.goal and program["place"] == answers.place
                  and program["level"] == answers.level and answers.days_per_week in program["supported_days"]]
    if not candidates:
        reasons.append("Для выбранного места программы пока нет.")
    elif answers.days_per_week not in (2, 3, 4):
        reasons.append("Готовые программы рассчитаны на 2, 3 или 4 занятия в неделю.")
    elif answers.days_per_week in (2, 3) and any((day % 7) + 1 in answers.weekdays for day in answers.weekdays):
        reasons.append("Между силовыми занятиями всего тела нужен день отдыха.")
    elif answers.days_per_week == 4 and sorted(answers.weekdays) != [1, 2, 4, 6]:
        reasons.append("Четырёхдневный план сейчас рассчитан на понедельник, вторник, четверг и субботу.")
    else:
        timed = [item for item in candidates if item["min_minutes"] <= answers.minutes_per_session]
        equipped = [item for item in timed if set(item["required_equipment"]) <= set(answers.equipment)]
        if equipped:
            program = max(equipped, key=lambda item: (item["min_minutes"], item["duration_weeks"]))
        elif not timed:
            reasons.append(f"Для этого места нужно не меньше {min(item['min_minutes'] for item in candidates)} минут на занятие.")
        else:
            closest = min(timed, key=lambda item: len(set(item["required_equipment"]) - set(answers.equipment)))
            missing = set(closest["required_equipment"]) - set(answers.equipment)
            equipment_names = {"low_bar": "низкая перекладина", "bench": "скамья", "machines": "тренажёры", "dumbbells": "гантели", "bands": "резинки", "barbell": "штанга"}
            reasons.append("Не хватает оборудования для этой программы: " + ", ".join(equipment_names[item] for item in sorted(missing)) + ".")
    if reasons:
        guide_id = ("sport-limitations" if answers.limitations else
                    "sport-strength" if answers.goal == "strength_gain" else
                    "sport-maintain" if answers.goal == "maintain" else
                    "sport-intermediate" if answers.level == "intermediate" else
                    "sport-schedule" if answers.days_per_week not in (2, 3, 4) or (answers.days_per_week in (2, 3) and any((day % 7) + 1 in answers.weekdays for day in answers.weekdays)) or (answers.days_per_week == 4 and sorted(answers.weekdays) != [1, 2, 4, 6]) else
                    "sport-short" if candidates and not any(item["min_minutes"] <= answers.minutes_per_session for item in candidates) else
                    "sport-equipment")
        guides = json.loads(files("app.content").joinpath("guides.json").read_text(encoding="utf-8"))
        material = next(item for item in guides if item["id"] == guide_id)
        return {"program": None, "sessions": [], "reasons": reasons, "material": material, "version": catalog["version"]}
    place_name = {"home": "дома", "outdoor": "на улице", "gym": "в зале"}[answers.place]
    goal_name = {"fat_loss_muscle_focus": "снижение веса с сохранением мышечной нагрузки",
                 "maintain": "поддержание формы", "strength_gain": "развитие силы"}[answers.goal]
    return {
        "program": program,
        "sessions": program["sessions"][: answers.days_per_week],
        "reasons": [],
        "why": [f"Цель: {goal_name}", f"Место: {place_name}", f"Занятий в неделю: {answers.days_per_week}"],
        "version": catalog["version"],
    }
