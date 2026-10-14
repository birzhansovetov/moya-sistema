"""Record when a plan was archived for limited restoration."""

from alembic import op
import sqlalchemy as sa

revision = "c419_plan_restore"
down_revision = "c418_matching_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sport_plans", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("study_plans", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("study_plans", "archived_at")
    op.drop_column("sport_plans", "archived_at")
