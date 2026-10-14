"""Persist an unfinished workout separately from completed training history."""

from alembic import op
import sqlalchemy as sa

revision = "c421_workout_drafts"
down_revision = "c420_training_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("sport_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("session_id", sa.String(8), nullable=False),
        sa.Column("actual", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "workout_date", "session_id", name="uq_workout_draft_occurrence"),
    )
    op.create_index("ix_workout_drafts_user_id", "workout_drafts", ["user_id"])
    op.create_index("ix_workout_drafts_plan_id", "workout_drafts", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_workout_drafts_plan_id", table_name="workout_drafts")
    op.drop_index("ix_workout_drafts_user_id", table_name="workout_drafts")
    op.drop_table("workout_drafts")
