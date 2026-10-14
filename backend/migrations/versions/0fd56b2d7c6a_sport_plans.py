"""sport plans and workout history

Revision ID: 0fd56b2d7c6a
Revises: 4b22f469c5f8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0fd56b2d7c6a"
down_revision: Union[str, None] = "4b22f469c5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sport_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_id", sa.String(80), nullable=False),
        sa.Column("content_version", sa.String(32), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("program_snapshot", sa.JSON(), nullable=False),
        sa.Column("active_key", sa.String(8), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "active_key", name="uq_sport_active_plan"),
    )
    op.create_index("ix_sport_plans_user_id", "sport_plans", ["user_id"])
    op.create_table(
        "workout_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("sport_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("session_id", sa.String(8), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "workout_date", "session_id", name="uq_workout_occurrence"),
    )
    op.create_index("ix_workout_logs_user_id", "workout_logs", ["user_id"])
    op.create_index("ix_workout_logs_plan_id", "workout_logs", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_workout_logs_plan_id", table_name="workout_logs")
    op.drop_index("ix_workout_logs_user_id", table_name="workout_logs")
    op.drop_table("workout_logs")
    op.drop_index("ix_sport_plans_user_id", table_name="sport_plans")
    op.drop_table("sport_plans")
