"""Private revisioned study drafts."""
from alembic import op
import sqlalchemy as sa

revision='c413_study_drafts'
down_revision='c412_study'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('study_drafts',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('plan_id',sa.String(36),sa.ForeignKey('study_plans.id',ondelete='CASCADE'),nullable=False),
        sa.Column('lesson_id',sa.String(60),nullable=False),
        sa.Column('content',sa.JSON(),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','plan_id','lesson_id',name='uq_study_draft_lesson'))
    op.create_index('ix_study_drafts_user_id','study_drafts',['user_id'])
    op.create_index('ix_study_drafts_plan_id','study_drafts',['plan_id'])


def downgrade():
    op.drop_index('ix_study_drafts_plan_id',table_name='study_drafts')
    op.drop_index('ix_study_drafts_user_id',table_name='study_drafts')
    op.drop_table('study_drafts')
