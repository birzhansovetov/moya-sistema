"""Owned, staged lesson assistance with authored fallback."""

from datetime import timedelta
from time import monotonic
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db, utc_now
from app.models import StudyAssistRequest, StudyAttempt, User
from app.study import course, owned_plan
from app.study_help import get_help_fragment
from app.study_assist import PROMPT_VERSION, assist_lesson
from app.assistant_learning import ExplainFormat, prepared_example, next_actions
from app.cloud_ai import explain_catalog_fragment, PROMPT_VERSION as CLOUD_PROMPT_VERSION
from app.rate_limit import enforce, record
from app.assistant_limits import reserve_cloud_call
from app.tasks import local_date

router = APIRouter(prefix="/api/study", tags=["study-assist"])


@router.get("/assist/availability")
def availability(plan_id: str, lesson_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    plan = owned_plan(db, user.id, plan_id)
    if lesson_id not in plan.lesson_ids:
        raise HTTPException(404, "Урок не найден")
    lesson = next((item for item in course(plan.course_id, plan.version)["lessons"] if item["id"] == lesson_id), None)
    if lesson is None:
        raise HTTPException(404, "Урок не найден")
    return {"question_indices": [index for index in range(len(lesson["quiz"]))
            if get_help_fragment(plan.course_id, plan.version, lesson_id, index,
                                 today=local_date(user.timezone), db=db) is not None]}


class AssistRequest(BaseModel):
    format: ExplainFormat = "default"
    plan_id: str
    lesson_id: str
    question_index: int = Field(ge=0)
    stage: Literal["explain", "hint", "next_step", "review"]
    attempt_id: str | None = None
    answer_text: str | None = Field(default=None, max_length=2000)
    include_answer: bool = False
    stage_token: str | None = None


class FeedbackRequest(BaseModel):
    request_id: str
    helped: bool


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered)-1, int((len(ordered)-1)*fraction + .5)))]


@router.post('/assist/feedback')
def feedback(payload: FeedbackRequest, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    item = db.get(StudyAssistRequest, payload.request_id)
    if item is None or item.user_id != context.user.id:
        raise HTTPException(404, 'Запрос не найден')
    if item.helped is not None:
        raise HTTPException(409, 'Оценка уже сохранена')
    item.helped = payload.helped
    db.commit()
    return {'saved': True}


@router.get('/assist/report')
def report(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if request.app.state.settings.environment != 'development' and request.app.state.settings.environment != 'test':
        raise HTTPException(404, 'Отчёт недоступен')
    rows = db.query(StudyAssistRequest).filter(StudyAssistRequest.user_id == user.id).all()
    groups: dict[tuple, list[StudyAssistRequest]] = {}
    for row in rows:
        groups.setdefault((row.course_id, row.version, row.lesson_id, row.question_index, row.stage), []).append(row)
    return {'total': len(rows), 'groups': [
        {'course_id': key[0], 'version': key[1], 'lesson_id': key[2], 'question_index': key[3], 'stage': key[4],
         'total': len(items), 'fallback_rate': sum(item.source == 'authored' for item in items)/len(items),
         'helped': sum(item.helped is True for item in items), 'not_helped': sum(item.helped is False for item in items),
         'p50_ms': _percentile([item.latency_ms for item in items], .5),
         'p95_ms': _percentile([item.latency_ms for item in items], .95)}
        for key, items in sorted(groups.items())]}


def _token(secret: str, user_id: str, plan_id: str, lesson_id: str, question_index: int, stage: str) -> str:
    return jwt.encode({"purpose": "study-assist-stage", "sub": user_id, "plan": plan_id,
                       "lesson": lesson_id, "question": question_index, "stage": stage,
                       "exp": utc_now() + timedelta(minutes=15)}, secret, algorithm="HS256")


def _check_token(secret: str, token: str | None, user_id: str, plan_id: str,
                 lesson_id: str, question_index: int, stage: str) -> None:
    try:
        claims = jwt.decode(token or "", secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(403, "Сначала откройте предыдущую подсказку") from None
    if (claims.get("purpose"), claims.get("sub"), claims.get("plan"), claims.get("lesson"),
            claims.get("question"), claims.get("stage")) != (
            "study-assist-stage", user_id, plan_id, lesson_id, question_index, stage):
        raise HTTPException(403, "Сначала откройте предыдущую подсказку")


@router.post("/assist")
def assist(payload: AssistRequest, request: Request, context: AuthContext = Depends(require_csrf),
           db: Session = Depends(get_db)):
    started = monotonic()
    plan = owned_plan(db, context.user.id, payload.plan_id)
    if payload.lesson_id not in plan.lesson_ids:
        raise HTTPException(404, "Урок не найден")
    fragment = get_help_fragment(plan.course_id, plan.version, payload.lesson_id, payload.question_index,
                                 today=local_date(context.user.timezone), db=db)
    if fragment is None:
        raise HTTPException(404, "Для этого вопроса пока нет проверенной подсказки")
    secret = request.app.state.settings.jwt_secret
    if payload.stage in ("next_step", "review"):
        _check_token(secret, payload.stage_token, context.user.id, plan.id, payload.lesson_id,
                     payload.question_index, payload.stage)
    item = db.get(StudyAttempt, payload.attempt_id) if payload.attempt_id else None
    if item and (item.user_id != context.user.id or item.plan_id != plan.id or item.lesson_id != payload.lesson_id):
        item = None
    if payload.stage == "review":
        if not item or item.user_id != context.user.id or item.plan_id != plan.id or item.lesson_id != payload.lesson_id:
            raise HTTPException(403, "Сначала сохраните собственную попытку")
    next_stage = {"hint": "next_step", "next_step": "review"}.get(payload.stage)
    settings = request.app.state.settings
    allowed = {value.strip() for value in settings.local_ai_study_routes.split(",") if value.strip()}
    generated = None
    if settings.local_ai_enabled and settings.environment == "development" and plan.course_id in allowed:
        try:
            enforce(db, request, "study_assist", context.user.id, account_limit=20, source_limit=1000, minutes=60)
            record(db, request, "study_assist", context.user.id)
            generated = assist_lesson(fragment, stage=payload.stage, course_id=plan.course_id, locale="ru",
                                      attempt=item, model=settings.ollama_model,
                                      model_digest=settings.ollama_model_digest,
                                      answer_text=payload.answer_text if payload.stage == 'review' and item and payload.include_answer else None)
        except HTTPException as error:
            if error.status_code != 429:
                raise
    if generated is None and settings.cloud_ai_enabled and settings.gemini_api_key and payload.stage != 'review':
        try:
            reserve_cloud_call(db, context.user, request)
            generated = explain_catalog_fragment(fragment, stage=payload.stage,
                api_key=settings.gemini_api_key, model=settings.gemini_model, format=payload.format,
                prepared_example=(next(x for x in course(plan.course_id,plan.version)["lessons"] if x["id"]==payload.lesson_id).get("example") if payload.format=="example" else None))
        except HTTPException as error:
            if error.status_code != 429:
                raise
    if generated is None:
        generated = {"source": "authored", "text": {"hint": fragment.hint, "next_step": fragment.next_step,
                     "review": fragment.explanation, "explain": fragment.explanation}[payload.stage],
                     "next_step": ""}
    metric = StudyAssistRequest(user_id=context.user.id, course_id=plan.course_id, version=plan.version,
                                lesson_id=payload.lesson_id, question_index=payload.question_index,
                                stage=payload.stage, source=generated['source'], prompt_version=CLOUD_PROMPT_VERSION if generated['source'] == 'cloud_ai' else PROMPT_VERSION,
                                model_digest=(settings.ollama_model_digest if generated['source'] == 'local_ai' else settings.gemini_model if generated['source'] == 'cloud_ai' else ''),
                                latency_ms=round((monotonic()-started)*1000))
    db.add(metric)
    db.commit()
    return {"format":payload.format, "request_id": metric.id, "source": generated["source"], "stage": payload.stage, "text": generated["text"], "next_step": generated["next_step"],
            "lesson_id": payload.lesson_id, "version": plan.version, "question_index": payload.question_index,
            "allow_local_answer": settings.local_ai_enabled and settings.environment == "development" and plan.course_id in allowed,
            "next_stage_token": _token(secret, context.user.id, plan.id, payload.lesson_id,
                                       payload.question_index, next_stage) if next_stage else None}
