"""Save one training rating per plan and completed week."""

from alembic import op
import sqlalchemy as sa

revision = "c420_training_feedback"
down_revision = "c419_plan_restore"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("sport_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "week_end", name="uq_training_feedback_plan_week"),
    )
    op.create_index("ix_training_feedback_user_id", "training_feedback", ["user_id"])
    op.create_index("ix_training_feedback_plan_id", "training_feedback", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_training_feedback_plan_id", table_name="training_feedback")
    op.drop_index("ix_training_feedback_user_id", table_name="training_feedback")
    op.drop_table("training_feedback")
