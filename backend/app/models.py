from datetime import date, datetime
from datetime import date as DateValue
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utc_now


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Almaty")
    hidden_sections: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    hidden_spheres: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    finance_currency: Mapped[str] = mapped_column(String(3), default="KZT", server_default="KZT")
    onboarding_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    onboarding_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    sessions: Mapped[list["LoginSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ContentRevocation(Base):
    __tablename__ = "content_revocations"
    __table_args__ = (UniqueConstraint("kind", "item_id", "version", name="uq_content_revocation_variant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(24))
    item_id: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ContentRevocationEvent(Base):
    __tablename__ = "content_revocation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(24))
    item_id: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(12))
    actor: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MatchingPreview(Base):
    __tablename__ = "matching_previews"
    __table_args__ = (UniqueConstraint("user_id", "nonce_hash", name="uq_matching_preview_nonce"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), unique=True)
    survey_version: Mapped[int] = mapped_column(Integer)
    answers: Mapped[dict] = mapped_column(JSON)
    answers_digest: Mapped[str] = mapped_column(String(64))
    candidates: Mapped[dict] = mapped_column(JSON)
    areas: Mapped[dict] = mapped_column(JSON)
    expected_active: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class MatchingStartResult(Base):
    __tablename__ = "matching_start_results"
    __table_args__ = (UniqueConstraint("user_id", "nonce_hash", name="uq_matching_start_nonce"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload_digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class EmailToken(Base):
    __tablename__ = "email_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_email_token_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthRateEvent(Base):
    __tablename__ = "auth_rate_events"
    __table_args__ = (Index("ix_auth_rate_events_lookup", "action", "key_hash", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    action: Mapped[str] = mapped_column(String(24))
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("user_id", "create_key", name="uq_task_create_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    create_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    create_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    section: Mapped[str] = mapped_column(String(32), default="personal")
    due_date: Mapped[DateValue | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(12), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="todo")
    recurrence: Mapped[str] = mapped_column(String(12), default="none")
    weekdays: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    subtasks: Mapped[list["Subtask"]] = relationship(back_populates="task", cascade="all, delete-orphan", order_by="Subtask.position")
    completions: Mapped[list["TaskCompletion"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    position: Mapped[int] = mapped_column(Integer)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    task: Mapped[Task] = relationship(back_populates="subtasks")


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    __table_args__ = (UniqueConstraint("task_id", "occurrence_date", name="uq_task_occurrence_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    occurrence_date: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    task: Mapped[Task] = relationship(back_populates="completions")


class SportPlan(Base):
    __tablename__ = "sport_plans"
    __table_args__ = (UniqueConstraint("user_id", "active_key", name="uq_sport_active_plan"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[str] = mapped_column(String(80))
    content_version: Mapped[str] = mapped_column(String(32))
    answers: Mapped[dict] = mapped_column(JSON)
    program_snapshot: Mapped[dict] = mapped_column(JSON)
    active_key: Mapped[str | None] = mapped_column(String(8), nullable=True)
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WorkoutLog(Base):
    __tablename__ = "workout_logs"
    __table_args__ = (UniqueConstraint("plan_id", "workout_date", "session_id", name="uq_workout_occurrence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("sport_plans.id", ondelete="CASCADE"), index=True)
    workout_date: Mapped[date] = mapped_column(Date)
    session_id: Mapped[str] = mapped_column(String(8))
    results: Mapped[list[dict]] = mapped_column(JSON)
    difficulty: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WorkoutDraft(Base):
    __tablename__ = "workout_drafts"
    __table_args__ = (UniqueConstraint("plan_id", "workout_date", "session_id", name="uq_workout_draft_occurrence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("sport_plans.id", ondelete="CASCADE"), index=True)
    workout_date: Mapped[date] = mapped_column(Date)
    session_id: Mapped[str] = mapped_column(String(8))
    actual: Mapped[dict] = mapped_column(JSON, default=dict)
    difficulty: Mapped[int] = mapped_column(Integer, default=5)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class TrainingFeedback(Base):
    __tablename__ = "training_feedback"
    __table_args__ = (UniqueConstraint("plan_id", "week_end", name="uq_training_feedback_plan_week"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("sport_plans.id", ondelete="CASCADE"), index=True)
    week_end: Mapped[date] = mapped_column(Date)
    rating: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NutritionProfile(Base):
    __tablename__ = "nutrition_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    answers: Mapped[dict] = mapped_column(JSON)
    preferences: Mapped[dict] = mapped_column(JSON)
    estimate_snapshot: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NutritionMenu(Base):
    __tablename__ = "nutrition_menus"
    __table_args__ = (UniqueConstraint("user_id", "active_key", name="uq_nutrition_active_menu"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_key: Mapped[str | None] = mapped_column(String(8), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    days_snapshot: Mapped[list[dict]] = mapped_column(JSON)
    profile_snapshot: Mapped[dict] = mapped_column(JSON)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class FoodLog(Base):
    __tablename__ = "food_logs"
    __table_args__ = (UniqueConstraint("user_id", "create_key", name="uq_food_log_create_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    create_key: Mapped[str] = mapped_column(String(100))
    log_date: Mapped[date] = mapped_column(Date)
    recipe_id: Mapped[str] = mapped_column(String(80))
    portions: Mapped[float] = mapped_column()
    recipe_snapshot: Mapped[dict] = mapped_column(JSON)
    nutrition_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date", name="uq_weight_log_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    log_date: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_expense_category_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=100)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("user_id", "create_key", name="uq_expense_create_key"),
        Index("ix_expenses_scope_date", "user_id", "currency", "expense_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[str] = mapped_column(ForeignKey("expense_categories.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    expense_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(500), default="")
    note_search: Mapped[str] = mapped_column(String(1000), default="")
    create_key: Mapped[str] = mapped_column(String(100))
    create_fingerprint: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PersonalEntry(Base):
    __tablename__ = 'personal_entries'
    __table_args__ = (UniqueConstraint('user_id', 'create_key', name='uq_personal_create_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(160), default='')
    body: Mapped[str] = mapped_column(Text, default='')
    date: Mapped[DateValue | None] = mapped_column(Date, nullable=True)
    mood: Mapped[str | None] = mapped_column(String(12), nullable=True)
    activity: Mapped[str] = mapped_column(String(12), default='other')
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    impression: Mapped[str] = mapped_column(Text, default='')
    search_text: Mapped[str] = mapped_column(Text, default='')
    create_key: Mapped[str] = mapped_column(String(100))
    create_fingerprint: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ReadingBook(Base):
    __tablename__ = 'reading_books'
    __table_args__ = (UniqueConstraint('user_id', 'create_key', name='uq_reading_book_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(160), default='')
    pages: Mapped[int] = mapped_column(Integer)
    initial_page: Mapped[int] = mapped_column(Integer, default=0)
    daily_pages: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(12), default='want')
    start_date: Mapped[DateValue | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[DateValue | None] = mapped_column(Date, nullable=True)
    cover_url: Mapped[str] = mapped_column(String(2000), default='')
    final_impression: Mapped[str] = mapped_column(Text, default='')
    create_key: Mapped[str] = mapped_column(String(100))
    create_fingerprint: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ReadingLog(Base):
    __tablename__ = 'reading_logs'
    __table_args__ = (UniqueConstraint('book_id', 'create_key', name='uq_reading_log_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    book_id: Mapped[str] = mapped_column(ForeignKey('reading_books.id', ondelete='CASCADE'), index=True)
    date: Mapped[DateValue] = mapped_column(Date)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter: Mapped[str] = mapped_column(String(200), default='')
    text: Mapped[str] = mapped_column(Text, default='')
    reflection: Mapped[dict] = mapped_column(JSON, default=dict)
    search_text: Mapped[str] = mapped_column(Text, default='')
    create_key: Mapped[str] = mapped_column(String(100))
    create_fingerprint: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class StudyPlan(Base):
    __tablename__ = 'study_plans'
    __table_args__ = (UniqueConstraint('user_id','create_key',name='uq_study_plan_key'), UniqueConstraint('user_id','active_slot',name='uq_study_active_slot'))
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    course_id: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    active_slot: Mapped[str | None] = mapped_column(String(40),nullable=True)
    config: Mapped[dict] = mapped_column(JSON)
    lesson_ids: Mapped[list] = mapped_column(JSON)
    create_key: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime,nullable=True)


class StudyAttempt(Base):
    __tablename__ = 'study_attempts'
    __table_args__ = (UniqueConstraint('user_id','create_key',name='uq_study_attempt_key'),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('study_plans.id',ondelete='CASCADE'),index=True)
    lesson_id: Mapped[str] = mapped_column(String(60))
    date: Mapped[DateValue] = mapped_column(Date)
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    passed: Mapped[bool] = mapped_column(Boolean)
    create_key: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


class StudyAssistRequest(Base):
    __tablename__ = 'study_assist_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    course_id: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    lesson_id: Mapped[str] = mapped_column(String(60))
    question_index: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(30))
    model_digest: Mapped[str] = mapped_column(String(120))
    latency_ms: Mapped[int] = mapped_column(Integer)
    helped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class StudyDraft(Base):
    __tablename__ = 'study_drafts'
    __table_args__ = (UniqueConstraint('user_id','plan_id','lesson_id',name='uq_study_draft_lesson'),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('study_plans.id',ondelete='CASCADE'),index=True)
    lesson_id: Mapped[str] = mapped_column(String(60))
    content: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer,default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now,onupdate=utc_now)


class StudyReview(Base):
    __tablename__ = 'study_reviews'
    __table_args__ = (UniqueConstraint('user_id','create_key',name='uq_study_review_key'),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    course_id: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    card_id: Mapped[str] = mapped_column(String(80))
    rating: Mapped[str] = mapped_column(String(20))
    streak: Mapped[int] = mapped_column(Integer)
    date: Mapped[DateValue] = mapped_column(Date)
    due_date: Mapped[DateValue] = mapped_column(Date)
    create_key: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


class BackupUse(Base):
    __tablename__ = "backup_uses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
