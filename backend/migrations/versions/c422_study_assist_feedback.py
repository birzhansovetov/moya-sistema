"""Metadata-only study assistance feedback."""

from alembic import op
import sqlalchemy as sa

revision = 'c422_study_assist_feedback'
down_revision = 'c421_workout_drafts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('study_assist_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.String(40), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('lesson_id', sa.String(60), nullable=False),
        sa.Column('question_index', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(20), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('prompt_version', sa.String(30), nullable=False),
        sa.Column('model_digest', sa.String(120), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('helped', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_study_assist_requests_user_id', 'study_assist_requests', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_study_assist_requests_user_id', table_name='study_assist_requests')
    op.drop_table('study_assist_requests')
