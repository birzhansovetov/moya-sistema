"""Optional localhost-only ranking of already reviewed onboarding choices."""

import json
import http.client
from collections import OrderedDict
from datetime import timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MatchingPreview, SportPlan, StudyAttempt, StudyPlan, TrainingFeedback, User, WorkoutLog
from app.tasks import local_date

PLAN_SPHERES = ("health", "education", "profession", "languages")


class PreviewAdvisor:
    """Bound local inference to one request at a time and three tries per preview."""

    def __init__(self):
        self._lock = Lock()
        self._busy = Lock()
        self._attempts: OrderedDict[str, int] = OrderedDict()
        self._results: OrderedDict[str, dict] = OrderedDict()

    def suggest(self, snapshot: MatchingPreview, *, enabled: bool, model: str,
                progress: dict | None = None) -> dict:
        if not enabled:
            return suggest_preview(snapshot, enabled=False, model=model)
        key = snapshot.nonce_hash
        with self._lock:
            if key in self._results:
                self._results.move_to_end(key)
                return self._results[key]
            if self._attempts.get(key, 0) >= 3:
                return suggest_preview(snapshot, enabled=False, model=model)
            if not self._busy.acquire(blocking=False):
                return suggest_preview(snapshot, enabled=False, model=model)
            self._attempts[key] = self._attempts.get(key, 0) + 1
            self._attempts.move_to_end(key)
            while len(self._attempts) > 128:
                self._attempts.popitem(last=False)
        try:
            result = suggest_preview(snapshot, enabled=True, model=model, progress=progress)
            if result["source"] == "local_ai":
                with self._lock:
                    self._results[key] = result
                    self._results.move_to_end(key)
                    while len(self._results) > 128:
                        self._results.popitem(last=False)
            return result
        finally:
            self._busy.release()


def completed_week_progress(db: Session, user: User) -> dict:
    """Only counts and difficulty from the last completed week; no free text."""
    today = local_date(user.timezone)
    end = today - timedelta(days=today.isoweekday())
    start = end - timedelta(days=6)
    workouts = db.scalars(select(WorkoutLog).where(
        WorkoutLog.user_id == user.id, WorkoutLog.workout_date >= start,
        WorkoutLog.workout_date <= end)).all()
    attempts = db.execute(select(StudyPlan.course_id, StudyAttempt).join(
        StudyAttempt, StudyAttempt.plan_id == StudyPlan.id).where(
        StudyAttempt.user_id == user.id, StudyAttempt.date >= start,
        StudyAttempt.date <= end)).all()
    study = {sphere: {"attempts": 0, "passed": 0} for sphere in ("education", "profession", "languages")}
    for course_id, attempt in attempts:
        sphere = ("education" if course_id in ("java", "go") else
                  "profession" if course_id == "java-backend" else
                  "languages" if course_id == "english" else None)
        if sphere:
            study[sphere]["attempts"] += 1
            study[sphere]["passed"] += int(attempt.passed)
            for question, answer in zip(attempt.snapshot.get("quiz", []), attempt.result.get("feedback", [])):
                if (isinstance(question, dict) and isinstance(answer, dict) and
                        not answer.get("correct") and isinstance(question.get("skill"), str)):
                    skill = question["skill"].strip()[:60]
                    if skill and skill not in study[sphere].setdefault("weak_skills", []) and len(study[sphere]["weak_skills"]) < 3:
                        study[sphere]["weak_skills"].append(skill)
    health = {
        "workouts": len(workouts),
        "average_difficulty": round(sum(item.difficulty for item in workouts) / len(workouts)) if workouts else None,
    }
    plan = db.scalar(select(SportPlan).where(SportPlan.user_id == user.id, SportPlan.active_key == "active"))
    if plan:
        health["current_program_id"] = plan.program_id
        feedback = db.scalar(select(TrainingFeedback).where(
            TrainingFeedback.user_id == user.id, TrainingFeedback.plan_id == plan.id,
            TrainingFeedback.week_end == end))
        if feedback:
            health["feedback"] = feedback.rating
    return {"week_end": end.isoformat(), "health": health, **study}


def _chat(model: str, prompt: str) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "Choose only supplied material IDs. Return JSON only. Do not create plans, exercises or medical advice."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": {"type": "object", "properties": {"recommendations": {"type": "array", "items": {
            "type": "object", "properties": {"sphere": {"type": "string"}, "id": {"type": "string"},
                                           "why": {"type": "string", "maxLength": 180}},
            "required": ["sphere", "id"], "additionalProperties": False}}},
            "required": ["recommendations"], "additionalProperties": False},
        "options": {"temperature": 0, "num_predict": 220, "num_ctx": 4096},
    }).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=45)
    try:
        connection.request("POST", "/api/chat", body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise OSError("local model unavailable")
        outer = json.loads(response.read())
    finally:
        connection.close()
    return json.loads(outer["message"]["content"])


def suggest_preview(snapshot: MatchingPreview, *, enabled: bool, model: str,
                    progress: dict | None = None) -> dict:
    available = {sphere: items for sphere in PLAN_SPHERES
                 if (items := snapshot.candidates.get(sphere, []))}
    chosen = {sphere: {"id": items[0]["id"], "title": items[0]["title"], "reason": items[0]["reason"], "source": "rules"}
              for sphere, items in available.items()}
    if not enabled or not available:
        return {"source": "rules", "recommendations": chosen, "progress_considered": False}

    answers = snapshot.answers
    # The saved candidate set already applied health and allergy filters. No raw
    # journal, expense, email, password or allergy codes enter this prompt.
    context = {
        "sport": {key: answers.get("health", {}).get("sport", {}).get(key)
                  for key in ("goal", "level", "place", "days_per_week", "minutes_per_session")}
                 if answers.get("health", {}).get("sport") else None,
        "education": {key: answers.get("education", {}).get(key) for key in ("track", "minutes")},
        "profession": {"track": answers.get("profession", {}).get("track")},
        "languages": {key: answers.get("languages", {}).get(key) for key in ("level", "goal", "minutes")},
    }
    choices = {sphere: [{"id": item["id"], "title": item["title"], "reason": item["reason"]}
                        for item in items] for sphere, items in available.items()}
    prompt = json.dumps({"task": "Выбери один подходящий ID для каждой сферы из списка с учётом записанного прогресса за последнюю завершённую неделю. Учитывай оценку сложности тренировки и темы ошибок в учёбе. Если безопасной лучшей альтернативы нет, оставь подходящий вариант. Для каждого выбора дай короткое объяснение why только по этим данным; не обещай результат и не давай медицинских советов. Ответь JSON.",
                         "answers": context, "progress": progress, "choices": choices}, ensure_ascii=False)
    try:
        response = _chat(model, prompt)
        proposals = response["recommendations"]
        if not isinstance(proposals, list):
            raise ValueError("invalid recommendations")
        proposed = chosen.copy()
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            sphere, item_id = proposal.get("sphere"), proposal.get("id")
            item = next((entry for entry in available.get(sphere, []) if entry["id"] == item_id), None)
            if item:
                why = proposal.get("why")
                explanation = (why.strip() if isinstance(why, str) and len(why) <= 180 and
                               all(char.isprintable() for char in why) else "")
                proposed[sphere] = {"id": item_id, "title": item["title"], "reason": item["reason"],
                                    "why": explanation or item["reason"], "source": "local_ai"}
    except (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException):
        return {"source": "rules", "recommendations": chosen, "progress_considered": False}
    source = "local_ai" if any(item["source"] == "local_ai" for item in proposed.values()) else "rules"
    considered = bool(progress and (progress["health"]["workouts"] or progress["health"].get("feedback") or
                                    any(progress[sphere]["attempts"] for sphere in ("education", "profession", "languages"))))
    return {"source": source, "recommendations": proposed, "progress_considered": considered}
