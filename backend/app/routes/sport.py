from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db
from app.db import utc_now
from app.content_review import is_revoked, revocation_reason
from app.models import SportPlan, User, WorkoutDraft, WorkoutLog
from app.sport import SportAnswers, load_sport_catalog, select_program


router = APIRouter(prefix="/api/health/sport", tags=["sport"])


class PlanRequest(BaseModel):
    answers: SportAnswers
    confirm_replace: bool = False


class ExerciseResult(BaseModel):
    exercise_id: str
    performed_exercise_id: str | None = None
    completed_sets: int = Field(ge=1, le=10)
    reps_per_set: list[int] = Field(min_length=1, max_length=10)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)


class WorkoutRequest(BaseModel):
    plan_id: str
    date: date
    session_id: str
    results: list[ExerciseResult] = Field(min_length=1)
    difficulty: int = Field(ge=1, le=10)
    note: str = Field(default="", max_length=1000)


class DraftExercise(BaseModel):
    sets: int = Field(ge=1, le=10)
    reps: list[str] = Field(max_length=10)
    weight: str = Field(max_length=12)
    performed: str | None = Field(default=None, max_length=80)


class WorkoutDraftRequest(BaseModel):
    plan_id: str
    date: date
    session_id: str
    actual: dict[str, DraftExercise] = Field(max_length=40)
    difficulty: int = Field(ge=1, le=10)
    note: str = Field(default="", max_length=1000)


def _today(user: User) -> date:
    return datetime.now(ZoneInfo(user.timezone)).date()


def _active_plan(db: Session, user_id: str) -> SportPlan | None:
    return db.scalar(select(SportPlan).where(SportPlan.user_id == user_id, SportPlan.active_key == "active"))


def _available_selection(db: Session, answers: SportAnswers) -> dict:
    catalog = load_sport_catalog()
    revoked = {item["id"] for item in catalog["programs"] if is_revoked(db, "sport", item["id"], catalog["version"])}
    return select_program(answers, revoked)


def _plan_info(plan: SportPlan, db: Session | None = None) -> dict:
    warning = revocation_reason(db, "sport", plan.program_id, plan.content_version) if db else None
    return {
        "id": plan.id,
        "program": plan.program_snapshot,
        "answers": plan.answers,
        "content_version": plan.content_version,
        "started_on": plan.started_on.isoformat(),
        "ended_on": plan.ended_on.isoformat() if plan.ended_on else None,
        "revoked": warning is not None,
        "revocation_reason": warning,
    }


def _log_info(log: WorkoutLog, plan: SportPlan) -> dict:
    session = next(item for item in plan.program_snapshot["sessions"] if item["id"] == log.session_id)
    return {"id": log.id, "plan_id": log.plan_id, "date": log.workout_date.isoformat(), "session_id": log.session_id,
            "program_title": plan.program_snapshot["title"], "session_title": session["title"],
            "results": log.results, "difficulty": log.difficulty, "note": log.note, "created_at": log.created_at.isoformat()}


def _last_day(plan: SportPlan) -> date:
    return plan.started_on + timedelta(weeks=plan.program_snapshot["duration_weeks"], days=-1)


def _draft_session(db: Session, user: User, plan_id: str, day: date, session_id: str):
    plan = db.get(SportPlan, plan_id)
    if plan is None or plan.user_id != user.id or plan.active_key != "active":
        raise HTTPException(status_code=404, detail="Активный план не найден")
    if day < plan.started_on or day > min(_today(user), _last_day(plan)):
        raise HTTPException(status_code=422, detail="Дата тренировки вне периода плана")
    session = next((item for item in plan.program_snapshot["sessions"][:plan.answers["days_per_week"]]
                    if item["id"] == session_id), None)
    if session is None:
        raise HTTPException(status_code=422, detail="Тренировка не входит в выбранный план")
    return plan, session


def _draft_info(draft: WorkoutDraft) -> dict:
    return {"id": draft.id, "plan_id": draft.plan_id, "date": draft.workout_date.isoformat(),
            "session_id": draft.session_id, "actual": draft.actual, "difficulty": draft.difficulty,
            "note": draft.note, "updated_at": draft.updated_at.isoformat()}


@router.get("/catalog")
def catalog(_user: User = Depends(get_current_user)):
    return load_sport_catalog()


@router.post("/match")
def match(answers: SportAnswers, _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _available_selection(db, answers)


@router.get("/plan")
def get_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _active_plan(db, user.id)
    return {"plan": _plan_info(plan, db) if plan else None}


@router.put("/plan")
def save_plan(payload: PlanRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    selection = _available_selection(db, payload.answers)
    if selection["program"] is None:
        raise HTTPException(status_code=422, detail="Подходящей готовой программы нет: " + " ".join(selection["reasons"]))
    existing = _active_plan(db, context.user.id)
    answer_data = payload.answers.model_dump()
    today = _today(context.user)
    if existing and existing.answers == answer_data and existing.program_id == selection["program"]["id"] and today <= _last_day(existing):
        return {"status": "unchanged", "plan": _plan_info(existing)}
    if existing and not payload.confirm_replace:
        return {"status": "preview", "plan": _plan_info(existing), "proposed": selection["program"]}
    if existing:
        existing.active_key = None
        existing.ended_on = today
        db.flush()
    plan = SportPlan(
        user_id=context.user.id, program_id=selection["program"]["id"], content_version=selection["version"],
        answers=answer_data, program_snapshot=selection["program"], active_key="active", started_on=today,
    )
    db.add(plan)
    db.commit()
    return {"status": "replaced" if existing else "saved", "plan": _plan_info(plan)}


@router.get("/workouts")
def get_workouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.execute(select(WorkoutLog, SportPlan).join(SportPlan, WorkoutLog.plan_id == SportPlan.id).where(WorkoutLog.user_id == user.id).order_by(WorkoutLog.workout_date.desc(), WorkoutLog.created_at.desc())).all()
    return {"items": [_log_info(log, plan) for log, plan in logs]}


@router.get("/draft")
def get_workout_draft(plan_id: str = Query(), date: date = Query(), session_id: str = Query(),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _draft_session(db, user, plan_id, date, session_id)
    draft = db.scalar(select(WorkoutDraft).where(WorkoutDraft.user_id == user.id,
        WorkoutDraft.plan_id == plan_id, WorkoutDraft.workout_date == date,
        WorkoutDraft.session_id == session_id))
    return {"draft": _draft_info(draft) if draft else None}


@router.put("/draft")
def save_workout_draft(payload: WorkoutDraftRequest, context: AuthContext = Depends(require_csrf),
                       db: Session = Depends(get_db)):
    plan, session = _draft_session(db, context.user, payload.plan_id, payload.date, payload.session_id)
    if db.scalar(select(WorkoutLog.id).where(WorkoutLog.plan_id == plan.id,
        WorkoutLog.workout_date == payload.date, WorkoutLog.session_id == payload.session_id)):
        raise HTTPException(status_code=409, detail="Эта тренировка уже завершена")
    allowed = {work["exercise_id"]: work for work in session["work"]}
    for exercise_id, entry in payload.actual.items():
        work = allowed.get(exercise_id)
        if work is None or entry.sets > work["sets"] + 1 or len(entry.reps) != entry.sets:
            raise HTTPException(status_code=422, detail="Черновик содержит упражнение вне плана")
        if any(value and (not value.isdigit() or int(value) > 1000) for value in entry.reps):
            raise HTTPException(status_code=422, detail="Проверьте повторения")
        if entry.weight and (not entry.weight.replace(".", "", 1).isdigit() or float(entry.weight) > 1000):
            raise HTTPException(status_code=422, detail="Проверьте вес")
    draft = db.scalar(select(WorkoutDraft).where(WorkoutDraft.plan_id == plan.id,
        WorkoutDraft.workout_date == payload.date, WorkoutDraft.session_id == payload.session_id))
    if draft is None:
        draft = WorkoutDraft(user_id=context.user.id, plan_id=plan.id,
            workout_date=payload.date, session_id=payload.session_id)
        db.add(draft)
    draft.actual = {key: value.model_dump(exclude_none=True) for key, value in payload.actual.items()}
    draft.difficulty = payload.difficulty
    draft.note = payload.note
    draft.updated_at = utc_now()
    db.commit()
    return {"draft": _draft_info(draft)}


@router.post("/workouts", status_code=201)
def log_workout(payload: WorkoutRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    plan = db.get(SportPlan, payload.plan_id)
    if plan is None or plan.user_id != context.user.id or plan.active_key != "active":
        raise HTTPException(status_code=404, detail="Активный план не найден")
    if payload.date > min(_today(context.user), _last_day(plan)) or payload.date < plan.started_on:
        raise HTTPException(status_code=422, detail="Дата тренировки вне периода плана")
    sessions = plan.program_snapshot["sessions"][: plan.answers["days_per_week"]]
    session = next((item for item in sessions if item["id"] == payload.session_id), None)
    if session is None:
        raise HTTPException(status_code=422, detail="Тренировка не входит в выбранный план")
    allowed = {work["exercise_id"]: work for work in session["work"]}
    results = [result.model_dump(exclude={"performed_exercise_id"} if result.performed_exercise_id is None else set()) for result in payload.results]
    if len({item["exercise_id"] for item in results}) != len(results):
        raise HTTPException(status_code=422, detail="Упражнение указано повторно")
    for item in results:
        exercise = allowed.get(item["exercise_id"])
        performed = item.get("performed_exercise_id")
        if performed is not None:
            original = load_sport_catalog()["exercises"].get(item["exercise_id"], {})
            compatible = any(option["exercise_id"] == performed and plan.answers["place"] in option["places"] and set(option["required_equipment"]) <= set(plan.answers["equipment"]) for option in original.get("alternatives", []))
            if not compatible or performed in allowed:
                raise HTTPException(status_code=422, detail="Замена упражнения недоступна для этого плана")
            item["performed_exercise_name"] = load_sport_catalog()["exercises"][performed]["name"]
        if exercise is None or item["completed_sets"] > exercise["sets"] + 1 or len(item["reps_per_set"]) != item["completed_sets"] or any(rep < 0 or rep > 1000 for rep in item["reps_per_set"]):
            raise HTTPException(status_code=422, detail="Результат упражнения не соответствует плану")
    existing = db.scalar(select(WorkoutLog).where(WorkoutLog.plan_id == plan.id, WorkoutLog.workout_date == payload.date, WorkoutLog.session_id == payload.session_id))
    note = payload.note.strip()
    if existing:
        if existing.results == results and existing.difficulty == payload.difficulty and existing.note == note:
            return _log_info(existing, plan)
        raise HTTPException(status_code=409, detail="Эта тренировка уже записана")
    log = WorkoutLog(user_id=context.user.id, plan_id=plan.id, workout_date=payload.date, session_id=payload.session_id,
                     results=results, difficulty=payload.difficulty, note=note)
    db.add(log)
    draft = db.scalar(select(WorkoutDraft).where(WorkoutDraft.plan_id == plan.id,
        WorkoutDraft.workout_date == payload.date, WorkoutDraft.session_id == payload.session_id))
    if draft:
        db.delete(draft)
    db.commit()
    return _log_info(log, plan)
