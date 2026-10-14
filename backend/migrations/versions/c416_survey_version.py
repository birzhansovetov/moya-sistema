"""Version saved onboarding answers.

Revision ID: c416_survey_version
Revises: c415_onboarding
"""
from alembic import op
import sqlalchemy as sa

revision = "c416_survey_version"
down_revision = "c415_onboarding"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("onboarding_version", sa.Integer(), nullable=True))
    op.execute("UPDATE users SET onboarding_version = 1 WHERE onboarding_answers IS NOT NULL")


def downgrade():
    op.drop_column("users", "onboarding_version")
