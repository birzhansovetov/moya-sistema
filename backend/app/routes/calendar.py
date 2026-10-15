from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.auth import AuthContext, require_csrf
from app.db import get_db
from app.db import utc_now
from app.models import (Expense, FoodLog, PersonalEntry, ReadingBook, ReadingLog,
                        SportPlan, StudyAttempt, StudyPlan, StudyReview, Task, TaskCompletion, TrainingFeedback, User, WorkoutLog)
from app.tasks import days_between, local_date, occurs_on


router = APIRouter(prefix="/api/calendar", tags=["calendar"])
AREAS = ("health", "education", "profession", "languages", "finance", "personal")


def study_area(course_id: str) -> str | None:
    if course_id in ('java', 'go', 'java-backend'):
        return 'profession'
    if course_id in ('english', 'kazakh', 'korean', 'turkish', 'spanish'):
        return 'languages'
    return None


class FeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end: date
    rating: Literal["fits", "too_easy", "too_hard"]


def training_week_review(db: Session, user_id: str, start: date, end: date) -> dict | None:
    plan = db.scalar(select(SportPlan).where(SportPlan.user_id == user_id, SportPlan.active_key == 'active'))
    if not plan:
        return None
    weekdays = plan.answers.get('weekdays', [])
    sessions = plan.program_snapshot.get('sessions', [])
    duration = plan.program_snapshot.get('duration_weeks', 0)
    last_day = plan.started_on + timedelta(weeks=duration, days=-1)
    expected = {(day, sessions[weekdays.index(day.isoweekday())]['id'])
                for day in days_between(start, end)
                if plan.started_on <= day <= last_day and day.isoweekday() in weekdays
                and weekdays.index(day.isoweekday()) < len(sessions)}
    if not expected:
        return None
    feedback = db.scalar(select(TrainingFeedback).where(
        TrainingFeedback.user_id == user_id, TrainingFeedback.plan_id == plan.id,
        TrainingFeedback.week_end == end))
    logs = db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user_id,
        WorkoutLog.plan_id == plan.id, WorkoutLog.workout_date >= start,
        WorkoutLog.workout_date <= end)).all()
    expected_sessions = {session_id for _, session_id in expected}
    completed_logs = [log for log in logs if log.session_id in expected_sessions]
    completed = len({log.session_id for log in completed_logs})
    planned = len(expected)
    difficulty = round(sum(log.difficulty for log in completed_logs) / len(completed_logs)) if completed_logs else None
    if planned >= 3 and completed <= planned // 2:
        suggestion = 'review_frequency'
        suggested_days = len(weekdays) - 1
        reason = (f'За неделю записана {completed} из {planned} запланированных тренировок. '
                  f'Можно попробовать {suggested_days} занятия в неделю.')
    elif completed < planned:
        suggestion = 'keep'
        suggested_days = None
        reason = f'За неделю записана {completed} из {planned} тренировок. Повторите текущий ритм или измените дни, если расписание неудобно.'
    elif difficulty is not None and difficulty >= 8:
        suggestion = 'keep'
        suggested_days = None
        reason = 'Все занятия записаны, но нагрузка ощущалась высокой. Пока сохраните ритм и оцените восстановление.'
    else:
        suggestion = 'keep'
        suggested_days = None
        reason = 'Все занятия записаны. Текущий ритм можно сохранить и сравнить результаты через неделю.'
    result = {'plan_title': plan.program_snapshot.get('title', 'Программа тренировок'),
            'planned': planned, 'completed': completed, 'average_difficulty': difficulty,
            'suggestion': suggestion, 'suggested_days_per_week': suggested_days, 'reason': reason}
    if feedback:
        result['feedback'] = feedback.rating
    return result


@router.put('/weekly-review/feedback')
def save_training_feedback(payload: FeedbackPayload, context: AuthContext = Depends(require_csrf),
                           db: Session = Depends(get_db)):
    if payload.end > local_date(context.user.timezone) or payload.end.isoweekday() != 7:
        raise HTTPException(status_code=422, detail='Выберите завершённую неделю')
    if training_week_review(db, context.user.id, payload.end - timedelta(days=6), payload.end) is None:
        raise HTTPException(status_code=404, detail='План тренировок за эту неделю не найден')
    plan = db.scalar(select(SportPlan).where(SportPlan.user_id == context.user.id,
                                            SportPlan.active_key == 'active'))
    feedback = db.scalar(select(TrainingFeedback).where(
        TrainingFeedback.user_id == context.user.id, TrainingFeedback.plan_id == plan.id,
        TrainingFeedback.week_end == payload.end))
    if feedback is None:
        feedback = TrainingFeedback(user_id=context.user.id, plan_id=plan.id,
                                    week_end=payload.end, rating=payload.rating)
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.updated_at = utc_now()
    db.commit()
    return {'rating': feedback.rating, 'week_end': payload.end.isoformat()}


@router.get('/weekly-review')
def weekly_review(end: date = Query(), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_date(user.timezone)
    if end > today:
        raise HTTPException(status_code=422, detail='Неделя ещё не завершилась')
    start = end - timedelta(days=6)
    tasks = db.scalars(select(Task).where(Task.user_id == user.id)).all()
    task_ids = [task.id for task in tasks]
    completions = set()
    if task_ids:
        completions = {(row.task_id, row.occurrence_date) for row in db.scalars(
            select(TaskCompletion).where(TaskCompletion.task_id.in_(task_ids),
                                         TaskCompletion.occurrence_date >= start,
                                         TaskCompletion.occurrence_date <= end)).all()}
    planned = [(task.id, day) for day in days_between(start, end) for task in tasks if occurs_on(task, day)]

    def count(query):
        return db.scalar(select(func.count()).select_from(query.subquery())) or 0

    sport_count = count(select(WorkoutLog.id).where(WorkoutLog.user_id == user.id,
        WorkoutLog.workout_date >= start, WorkoutLog.workout_date <= end))
    food_count = count(select(FoodLog.id).where(FoodLog.user_id == user.id,
        FoodLog.log_date >= start, FoodLog.log_date <= end))
    attempts = db.execute(select(StudyPlan.course_id, StudyAttempt.id).join(
        StudyAttempt, StudyAttempt.plan_id == StudyPlan.id).where(
        StudyAttempt.user_id == user.id, StudyAttempt.date >= start, StudyAttempt.date <= end)).all()
    language_reviews = count(select(StudyReview.id).where(StudyReview.user_id == user.id,
        StudyReview.course_id.in_(('english', 'kazakh', 'korean', 'turkish', 'spanish')), StudyReview.date >= start, StudyReview.date <= end))
    reading_count = count(select(ReadingLog.id).join(ReadingBook).where(
        ReadingBook.user_id == user.id, ReadingBook.deleted_at.is_(None),
        ReadingLog.deleted_at.is_(None), ReadingLog.date >= start, ReadingLog.date <= end))
    finance_count = count(select(Expense.id).where(Expense.user_id == user.id,
        Expense.deleted_at.is_(None), Expense.expense_date >= start, Expense.expense_date <= end))
    personal_count = count(select(PersonalEntry.id).where(PersonalEntry.user_id == user.id,
        PersonalEntry.deleted_at.is_(None), PersonalEntry.kind == 'diary',
        PersonalEntry.date >= start, PersonalEntry.date <= end))
    return {
        'start': start.isoformat(), 'end': end.isoformat(),
        'tasks': {'planned': len(planned), 'completed': sum(key in completions for key in planned)},
        'training': training_week_review(db, user.id, start, end),
        'areas': {
            'health': sport_count + food_count,
            'education': reading_count,
            'profession': sum(study_area(course) == 'profession' for course, _ in attempts),
            'languages': language_reviews + sum(study_area(course) == 'languages' for course, _ in attempts),
            'finance': finance_count,
            'personal': personal_count,
        },
    }


@router.get('/analytics')
def four_week_analytics(end: date = Query(), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if end > local_date(user.timezone) or end.isoweekday() != 7:
        raise HTTPException(status_code=422, detail='Выберите завершённую неделю')
    start = end - timedelta(days=27)
    date_sources = (
        (select(TaskCompletion.occurrence_date).join(Task).where(Task.user_id == user.id), TaskCompletion.occurrence_date),
        (select(WorkoutLog.workout_date).where(WorkoutLog.user_id == user.id), WorkoutLog.workout_date),
        (select(FoodLog.log_date).where(FoodLog.user_id == user.id), FoodLog.log_date),
        (select(StudyAttempt.date).where(StudyAttempt.user_id == user.id), StudyAttempt.date),
        (select(StudyReview.date).where(StudyReview.user_id == user.id), StudyReview.date),
        (select(ReadingLog.date).join(ReadingBook).where(
            ReadingBook.user_id == user.id, ReadingBook.deleted_at.is_(None), ReadingLog.deleted_at.is_(None)), ReadingLog.date),
        (select(PersonalEntry.date).where(PersonalEntry.user_id == user.id,
            PersonalEntry.deleted_at.is_(None), PersonalEntry.kind == 'diary'), PersonalEntry.date),
        (select(Expense.expense_date).where(Expense.user_id == user.id, Expense.deleted_at.is_(None)), Expense.expense_date),
    )
    active_dates: set[date] = set()
    for source, day_column in date_sources:
        active_dates.update(db.scalars(source.where(day_column >= start, day_column <= end)).all())

    weeks = []
    for index in range(4):
        week_end = start + timedelta(days=index * 7 + 6)
        week_start = week_end - timedelta(days=6)
        review = weekly_review(end=week_end, user=user, db=db)
        review['active_days'] = sum(week_start <= day <= week_end for day in active_dates)
        review['workouts_logged'] = db.scalar(select(func.count(WorkoutLog.id)).where(
            WorkoutLog.user_id == user.id, WorkoutLog.workout_date >= week_start,
            WorkoutLog.workout_date <= week_end)) or 0
        weeks.append(review)
    return {'start': start.isoformat(), 'end': end.isoformat(), 'weeks': weeks,
            'summary': {
                'active_days': len(active_dates),
                'workouts_logged': sum(week['workouts_logged'] for week in weeks),
                'tasks': {'planned': sum(week['tasks']['planned'] for week in weeks),
                          'completed': sum(week['tasks']['completed'] for week in weeks)},
                'areas': {area: sum(week['areas'][area] for week in weeks) for area in AREAS},
            }}


@router.get("/streak")
def activity_streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = local_date(user.timezone)
    active = set()

    sources = (
        select(TaskCompletion.occurrence_date).join(Task).where(Task.user_id == user.id),
        select(WorkoutLog.workout_date).where(WorkoutLog.user_id == user.id),
        select(FoodLog.log_date).where(FoodLog.user_id == user.id),
        select(StudyAttempt.date).where(StudyAttempt.user_id == user.id),
        select(StudyReview.date).where(StudyReview.user_id == user.id),
        select(ReadingLog.date).join(ReadingBook).where(
            ReadingBook.user_id == user.id, ReadingBook.deleted_at.is_(None), ReadingLog.deleted_at.is_(None)),
        select(PersonalEntry.date).where(
            PersonalEntry.user_id == user.id, PersonalEntry.kind == 'diary',
            PersonalEntry.deleted_at.is_(None)),
        select(Expense.expense_date).where(Expense.user_id == user.id, Expense.deleted_at.is_(None)),
    )
    for query in sources:
        active.update(day for day in db.scalars(query).all() if day is not None and day <= today)

    cursor = today if today in active else today - timedelta(days=1)
    count = 0
    while cursor in active:
        count += 1
        cursor -= timedelta(days=1)
    last_seven = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    return {
        "today": today.isoformat(),
        "current_streak": count,
        "today_active": today in active,
        "days": [{"date": day.isoformat(), "active": day in active} for day in last_seven],
    }


@router.get("")
def calendar(
    start: date = Query(),
    end: date = Query(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end < start or (end - start).days > 90:
        raise HTTPException(status_code=422, detail="Укажите период до 90 дней")
    tasks = db.scalars(select(Task).where(Task.user_id == user.id)).all()
    task_ids = [task.id for task in tasks]
    completed = set()
    if task_ids:
        rows = db.scalars(select(TaskCompletion).where(TaskCompletion.task_id.in_(task_ids), TaskCompletion.occurrence_date >= start, TaskCompletion.occurrence_date <= end)).all()
        completed = {(item.task_id, item.occurrence_date) for item in rows}
    items = []
    for day in days_between(start, end):
        for task in tasks:
            scheduled = occurs_on(task, day)
            if scheduled or (task.id, day) in completed:
                items.append({
                    "task_id": task.id,
                    "title": task.title,
                    "date": day.isoformat(),
                    "completed": (task.id, day) in completed,
                    "historical": not scheduled,
                    "priority": task.priority,
                    "section": task.section,
                    "status": task.status,
                })
    personal = db.scalars(select(PersonalEntry).where(PersonalEntry.user_id == user.id, PersonalEntry.kind.in_(['event', 'experiment']), PersonalEntry.deleted_at.is_(None), PersonalEntry.date >= start, PersonalEntry.date <= end).order_by(PersonalEntry.date, PersonalEntry.created_at)).all()
    return {"items": items, "today": local_date(user.timezone).isoformat(), "personal_items": [
        {"id": entry.id, "title": entry.title, "date": entry.date.isoformat(), "kind": entry.kind, "completed": entry.completed} for entry in personal
    ]}
