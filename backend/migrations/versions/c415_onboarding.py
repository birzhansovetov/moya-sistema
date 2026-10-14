"""Store personalized onboarding choices.

Revision ID: c415_onboarding
Revises: c414_backup
"""
from alembic import op
import sqlalchemy as sa

revision = "c415_onboarding"
down_revision = "c414_backup"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("onboarding_answers", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))
    # Existing accounts retain access; only new registrations enter onboarding.
    op.execute("UPDATE users SET onboarding_completed_at = created_at WHERE verified_at IS NOT NULL")


def downgrade():
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "onboarding_answers")
