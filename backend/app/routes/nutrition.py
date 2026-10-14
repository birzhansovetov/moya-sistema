from copy import deepcopy
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db
from app.content_review import is_revoked, revocation_reason
from app.models import FoodLog, NutritionMenu, NutritionProfile, User, WeightLog
from app.nutrition import NutritionAnswers, NutritionPreferences, compatible_recipes, create_menu_days, estimate_nutrition, load_recipes, recipe_nutrition, snapshot_recipe, summarize_menu


router = APIRouter(prefix="/api/health/nutrition", tags=["nutrition"])


class ProfileRequest(BaseModel):
    answers: NutritionAnswers
    preferences: NutritionPreferences


class MenuRequest(BaseModel):
    start_date: date
    confirm_replace: bool = False


class MenuChange(BaseModel):
    date: date
    meal: Literal["breakfast", "lunch", "dinner"]
    recipe_id: str
    portions: float = Field(ge=0.5, le=4)


class FoodLogRequest(BaseModel):
    date: date
    recipe_id: str
    portions: float = Field(gt=0, le=4)
    create_key: str = Field(min_length=1, max_length=100)


class WeightLogRequest(BaseModel):
    date: date
    weight_kg: float = Field(ge=25, le=350)


def _today(user: User) -> date:
    return datetime.now(ZoneInfo(user.timezone)).date()


def _profile_info(profile: NutritionProfile) -> dict:
    return {"answers": profile.answers, "preferences": profile.preferences, "estimate": profile.estimate_snapshot["estimate"],
            "reasons": profile.estimate_snapshot["reasons"], "sources": profile.estimate_snapshot["sources"]}


def _active_menu(db: Session, user_id: str) -> NutritionMenu | None:
    return db.scalar(select(NutritionMenu).where(NutritionMenu.user_id == user_id, NutritionMenu.active_key == "active"))


def _menu_info(menu: NutritionMenu, profile: NutritionProfile | None, db: Session | None = None) -> dict:
    target = menu.profile_snapshot["estimate"]["target_kcal"]
    summary = summarize_menu(menu.days_snapshot, target)
    stale = profile is None or menu.profile_snapshot["answers"] != profile.answers or menu.profile_snapshot["preferences"] != profile.preferences
    version = menu.profile_snapshot.get("content_version", load_recipes()["version"])
    revoked = {} if db is None else {entry["recipe_id"]: reason for day in menu.days_snapshot for entry in day["meals"]
                                     if (reason := revocation_reason(db, "recipe", entry["recipe_id"], version))}
    return {"id": menu.id, "start_date": menu.start_date.isoformat(), "target_kcal": target, "stale": stale,
            "revoked": bool(revoked), "revoked_recipe_ids": sorted(revoked), "revocation_reasons": revoked, **summary}


def _log_info(log: FoodLog) -> dict:
    return {"id": log.id, "date": log.log_date.isoformat(), "recipe_id": log.recipe_id, "recipe": log.recipe_snapshot,
            "portions": log.portions, "nutrition": log.nutrition_snapshot, "created_at": log.created_at.isoformat()}


def _weight_info(log: WeightLog) -> dict:
    return {"id": log.id, "date": log.log_date.isoformat(), "weight_kg": log.weight_kg, "created_at": log.created_at.isoformat()}


@router.get("/recipes")
def recipes(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    catalog = load_recipes()
    return {**catalog, "recipes": [item for item in catalog["recipes"]
                                  if not is_revoked(db, "recipe", item["id"], catalog["version"])]}


@router.post("/estimate")
def estimate(answers: NutritionAnswers, _user: User = Depends(get_current_user)):
    return estimate_nutrition(answers)


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(NutritionProfile, user.id)
    return {"profile": _profile_info(profile) if profile else None}


@router.put("/profile")
def save_profile(payload: ProfileRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    try:
        compatible_recipes(payload.preferences)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    profile = db.get(NutritionProfile, context.user.id)
    result = estimate_nutrition(payload.answers)
    if profile is None:
        profile = NutritionProfile(user_id=context.user.id, answers=payload.answers.model_dump(), preferences=payload.preferences.model_dump(), estimate_snapshot=result)
        db.add(profile)
    else:
        profile.answers = payload.answers.model_dump()
        profile.preferences = payload.preferences.model_dump()
        profile.estimate_snapshot = result
    db.commit()
    return {"profile": _profile_info(profile)}


@router.get("/menu")
def get_menu(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(NutritionProfile, user.id)
    menu = _active_menu(db, user.id)
    return {"menu": _menu_info(menu, profile, db) if menu else None}


@router.post("/menu")
def save_menu(payload: MenuRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    profile = db.get(NutritionProfile, context.user.id)
    if profile is None or profile.estimate_snapshot["estimate"] is None:
        raise HTTPException(status_code=422, detail="Сначала сохраните подходящую анкету питания и расчёт")
    if payload.start_date < _today(context.user) or (payload.start_date - _today(context.user)).days > 14:
        raise HTTPException(status_code=422, detail="Начало меню должно быть сегодня или в ближайшие 14 дней")
    try:
        catalog = load_recipes()
        revoked_ids = {item["id"] for item in catalog["recipes"] if is_revoked(db, "recipe", item["id"], catalog["version"])}
        days = create_menu_days(payload.start_date, NutritionPreferences(**profile.preferences),
                                profile.estimate_snapshot["estimate"]["target_kcal"], revoked_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    current = _active_menu(db, context.user.id)
    if current and not payload.confirm_replace:
        return {"status": "preview", "menu": _menu_info(current, profile), "proposed": summarize_menu(days, profile.estimate_snapshot["estimate"]["target_kcal"])}
    if current:
        current.active_key = None
        current.ended_on = _today(context.user)
        db.flush()
    menu = NutritionMenu(user_id=context.user.id, active_key="active", start_date=payload.start_date, days_snapshot=days,
                         profile_snapshot={"answers": deepcopy(profile.answers), "preferences": deepcopy(profile.preferences), "estimate": deepcopy(profile.estimate_snapshot["estimate"]),
                                           "content_version": load_recipes()["version"]})
    db.add(menu)
    db.commit()
    return {"status": "replaced" if current else "saved", "menu": _menu_info(menu, profile)}


@router.patch("/menu")
def change_menu(payload: MenuChange, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    profile = db.get(NutritionProfile, context.user.id)
    current = _active_menu(db, context.user.id)
    if current is None or profile is None:
        raise HTTPException(status_code=404, detail="Меню не найдено")
    if _menu_info(current, profile)["stale"]:
        raise HTTPException(status_code=409, detail="Анкета изменилась; сначала создайте новое меню")
    matching = compatible_recipes(NutritionPreferences(**profile.preferences))[payload.meal]
    recipe = next((item for item in matching if item["id"] == payload.recipe_id), None)
    if recipe and is_revoked(db, "recipe", recipe["id"], load_recipes()["version"]):
        raise HTTPException(status_code=422, detail="Рецепт временно отозван")
    if recipe is None:
        raise HTTPException(status_code=422, detail="Это блюдо не подходит для выбранного приёма пищи или ограничений")
    days = deepcopy(current.days_snapshot)
    day = next((item for item in days if item["date"] == payload.date.isoformat()), None)
    if day is None:
        raise HTTPException(status_code=422, detail="Дата вне текущего меню")
    entry = next(item for item in day["meals"] if item["meal"] == payload.meal)
    entry.update({"recipe_id": recipe["id"], "portions": payload.portions, "recipe": snapshot_recipe(recipe)})
    current.active_key = None
    current.ended_on = _today(context.user)
    db.flush()
    changed = NutritionMenu(user_id=context.user.id, active_key="active", start_date=current.start_date,
                            days_snapshot=days, profile_snapshot=deepcopy(current.profile_snapshot))
    db.add(changed)
    db.commit()
    return {"menu": _menu_info(changed, profile)}


@router.get("/food-log")
def get_food_log(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.scalars(select(FoodLog).where(FoodLog.user_id == user.id).order_by(FoodLog.log_date.desc(), FoodLog.created_at.desc())).all()
    return {"items": [_log_info(item) for item in entries]}


@router.post("/food-log", status_code=201)
def add_food_log(payload: FoodLogRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    if payload.date > _today(context.user):
        raise HTTPException(status_code=422, detail="Нельзя записать будущий приём пищи")
    existing = db.scalar(select(FoodLog).where(FoodLog.user_id == context.user.id, FoodLog.create_key == payload.create_key))
    if existing:
        if existing.log_date == payload.date and existing.recipe_id == payload.recipe_id and existing.portions == payload.portions:
            return _log_info(existing)
        raise HTTPException(status_code=409, detail="Этот ключ уже использован для другой записи")
    recipe = next((item for item in load_recipes()["recipes"] if item["id"] == payload.recipe_id), None)
    if recipe is None:
        raise HTTPException(status_code=422, detail="Рецепт не найден")
    if is_revoked(db, "recipe", recipe["id"], load_recipes()["version"]):
        raise HTTPException(status_code=422, detail="Рецепт временно отозван")
    saved = FoodLog(user_id=context.user.id, create_key=payload.create_key, log_date=payload.date, recipe_id=recipe["id"],
                    portions=payload.portions, recipe_snapshot=snapshot_recipe(recipe), nutrition_snapshot=recipe_nutrition(recipe, payload.portions))
    db.add(saved)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(select(FoodLog).where(FoodLog.user_id == context.user.id, FoodLog.create_key == payload.create_key))
        if raced and raced.log_date == payload.date and raced.recipe_id == payload.recipe_id and raced.portions == payload.portions:
            return _log_info(raced)
        raise HTTPException(status_code=409, detail="Этот ключ уже использован для другой записи") from None
    return _log_info(saved)


@router.get("/weight-log")
def get_weight_log(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.scalars(select(WeightLog).where(WeightLog.user_id == user.id).order_by(WeightLog.log_date.desc())).all()
    return {"items": [_weight_info(item) for item in entries]}


@router.post("/weight-log", status_code=201)
def add_weight_log(payload: WeightLogRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    if payload.date > _today(context.user):
        raise HTTPException(status_code=422, detail="Нельзя записать будущий вес")
    existing = db.scalar(select(WeightLog).where(WeightLog.user_id == context.user.id, WeightLog.log_date == payload.date))
    if existing:
        if existing.weight_kg == payload.weight_kg:
            return _weight_info(existing)
        raise HTTPException(status_code=409, detail="Вес за этот день уже записан")
    saved = WeightLog(user_id=context.user.id, log_date=payload.date, weight_kg=payload.weight_kg)
    db.add(saved)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(select(WeightLog).where(WeightLog.user_id == context.user.id, WeightLog.log_date == payload.date))
        if raced and raced.weight_kg == payload.weight_kg:
            return _weight_info(raced)
        raise HTTPException(status_code=409, detail="Вес за этот день уже записан") from None
    return _weight_info(saved)
