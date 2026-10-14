from datetime import date
from hashlib import sha256
from typing import Literal
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db, utc_now
from app.models import Subtask, Task, TaskCompletion, User
from app.tasks import occurs_on


router = APIRouter(prefix="/api/tasks", tags=["tasks"])
Priority = Literal["low", "medium", "high"]
TaskStatus = Literal["todo", "in_progress", "done"]
Recurrence = Literal["none", "daily", "weekly", "weekdays"]
Section = Literal["personal", "sport", "nutrition", "education", "work", "finance", "other"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    section: Section = "personal"
    due_date: date | None = None
    priority: Priority = "medium"
    recurrence: Recurrence = "none"
    weekdays: list[int] | None = None
    subtasks: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.recurrence != "none" and self.due_date is None:
            raise ValueError("Для повторения укажите дату начала")
        if self.recurrence == "weekdays":
            if not self.weekdays or len(set(self.weekdays)) != len(self.weekdays) or any(day < 0 or day > 6 for day in self.weekdays):
                raise ValueError("Укажите дни недели от 0 до 6 без повторов")
        if any(not value.strip() or len(value) > 160 for value in self.subtasks):
            raise ValueError("Название подзадачи должно содержать от 1 до 160 символов")
        return self


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    section: Section | None = None
    due_date: date | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    recurrence: Recurrence | None = None
    weekdays: list[int] | None = None


class SubtaskPatch(BaseModel):
    completed: bool


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class CompleteBody(BaseModel):
    completed: bool


def task_for_user(db: Session, user_id: str, task_id: str) -> Task:
    task = db.scalar(select(Task).options(selectinload(Task.subtasks)).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


def task_info(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "section": task.section,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "priority": task.priority,
        "status": task.status,
        "recurrence": task.recurrence,
        "weekdays": task.weekdays,
        "subtasks": [{"id": item.id, "title": item.title, "completed": item.completed} for item in task.subtasks],
    }


@router.get("")
def list_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.scalars(select(Task).options(selectinload(Task.subtasks)).where(Task.user_id == user.id).order_by(Task.created_at.desc())).all()
    return {"items": [task_info(task) for task in tasks]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    response: Response,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(min_length=8, max_length=100),
):
    fingerprint = sha256(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    existing = db.scalar(select(Task).options(selectinload(Task.subtasks)).where(Task.user_id == context.user.id, Task.create_key == idempotency_key))
    if existing is not None:
        if existing.create_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Этот ключ уже использован для другой версии задачи")
        response.status_code = 200
        return task_info(existing)
    task = Task(
        user_id=context.user.id,
        create_key=idempotency_key,
        create_fingerprint=fingerprint,
        title=payload.title.strip(),
        description=payload.description.strip(),
        section=payload.section,
        due_date=payload.due_date,
        priority=payload.priority,
        recurrence=payload.recurrence,
        weekdays=payload.weekdays,
    )
    if not task.title:
        raise HTTPException(status_code=422, detail="Введите название задачи")
    task.subtasks = [Subtask(title=value.strip(), position=index) for index, value in enumerate(payload.subtasks)]
    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalar(select(Task).options(selectinload(Task.subtasks)).where(Task.user_id == context.user.id, Task.create_key == idempotency_key))
        if prior is None:
            raise
        if prior.create_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Этот ключ уже использован для другой версии задачи") from None
        response.status_code = 200
        return task_info(prior)
    db.refresh(task)
    return task_info(task)


@router.get("/{task_id}")
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return task_info(task_for_user(db, user.id, task_id))


@router.patch("/{task_id}")
def update_task(task_id: str, payload: TaskPatch, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    old_date = task.due_date
    old_recurrence = task.recurrence
    old_status = task.status
    for field_name in payload.model_fields_set:
        value = getattr(payload, field_name)
        if value is None and field_name != "due_date":
            raise HTTPException(status_code=422, detail="Недопустимое значение поля")
        setattr(task, field_name, value.strip() if field_name in {"title", "description"} and isinstance(value, str) else value)
    if not task.title or (task.recurrence != "none" and task.due_date is None):
        raise HTTPException(status_code=422, detail="Проверьте название и дату повторения")
    if task.recurrence == "weekdays" and (not task.weekdays or any(day < 0 or day > 6 for day in task.weekdays)):
        raise HTTPException(status_code=422, detail="Проверьте дни недели")
    schedule_changed = task.due_date != old_date or task.recurrence != old_recurrence
    status_changed = "status" in payload.model_fields_set and task.status != old_status
    if schedule_changed and not status_changed:
        if task.recurrence != "none":
            task.status = "todo"
        elif task.due_date is not None:
            completion = db.scalar(select(TaskCompletion).where(TaskCompletion.task_id == task.id, TaskCompletion.occurrence_date == task.due_date))
            task.status = "done" if completion is not None else "todo"
        elif old_status == "done":
            task.status = "todo"
    if task.recurrence != "none" and task.status == "done":
        raise HTTPException(status_code=422, detail="Повторяющиеся задачи выполняются отдельно по датам")
    if task.recurrence == "none" and task.due_date is not None and "status" in payload.model_fields_set:
        current = db.scalar(select(TaskCompletion).where(TaskCompletion.task_id == task.id, TaskCompletion.occurrence_date == task.due_date))
        if task.status == "done" and current is None:
            db.add(TaskCompletion(task_id=task.id, occurrence_date=task.due_date))
        elif task.status != "done" and current is not None:
            db.delete(current)
    task.updated_at = utc_now()
    db.commit()
    return task_info(task)


@router.patch("/{task_id}/subtasks/{subtask_id}")
def update_subtask(task_id: str, subtask_id: str, payload: SubtaskPatch, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    subtask = next((item for item in task.subtasks if item.id == subtask_id), None)
    if subtask is None:
        raise HTTPException(status_code=404, detail="Подзадача не найдена")
    subtask.completed = payload.completed
    db.commit()
    return {"id": subtask.id, "title": subtask.title, "completed": subtask.completed}


@router.post("/{task_id}/subtasks", status_code=201)
def add_subtask(task_id: str, payload: SubtaskCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    title = payload.title.strip()
    if not title or len(task.subtasks) >= 30:
        raise HTTPException(status_code=422, detail="Проверьте название и количество подзадач")
    position = max((item.position for item in task.subtasks), default=-1) + 1
    subtask = Subtask(task_id=task.id, title=title, position=position)
    db.add(subtask)
    db.commit()
    return {"id": subtask.id, "title": subtask.title, "completed": subtask.completed}


@router.delete("/{task_id}/subtasks/{subtask_id}", status_code=204)
def delete_subtask(task_id: str, subtask_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    subtask = next((item for item in task.subtasks if item.id == subtask_id), None)
    if subtask is None:
        raise HTTPException(status_code=404, detail="Подзадача не найдена")
    db.delete(subtask)
    db.commit()
    return Response(status_code=204)


@router.post("/{task_id}/occurrences/{day}/complete")
def complete_occurrence(task_id: str, day: date, payload: CompleteBody, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    entry = db.scalar(select(TaskCompletion).where(TaskCompletion.task_id == task_id, TaskCompletion.occurrence_date == day))
    if not occurs_on(task, day) and (payload.completed or entry is None):
        raise HTTPException(status_code=422, detail="На эту дату задача не запланирована")
    if payload.completed and entry is None:
        db.add(TaskCompletion(task_id=task_id, occurrence_date=day))
    elif not payload.completed and entry is not None:
        db.delete(entry)
    if task.recurrence == "none" and task.due_date == day:
        task.status = "done" if payload.completed else "todo"
    db.commit()
    return {"task_id": task_id, "date": day.isoformat(), "completed": payload.completed}


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    task = task_for_user(db, context.user.id, task_id)
    db.delete(task)
    db.commit()
    return Response(status_code=204)
