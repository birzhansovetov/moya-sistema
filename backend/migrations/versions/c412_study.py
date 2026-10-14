"""Private study plans, immutable lesson attempts and vocabulary reviews."""
from alembic import op
import sqlalchemy as sa
revision='c412_study'
down_revision='c411_reading'
branch_labels=None
depends_on=None


def common():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('create_key',sa.String(100),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False)]


def upgrade():
    op.create_table('study_plans',*common(),sa.Column('course_id',sa.String(40),nullable=False),sa.Column('version',sa.String(20),nullable=False),sa.Column('active_slot',sa.String(40),nullable=True),sa.Column('config',sa.JSON(),nullable=False),sa.Column('lesson_ids',sa.JSON(),nullable=False),sa.UniqueConstraint('user_id','create_key',name='uq_study_plan_key'),sa.UniqueConstraint('user_id','active_slot',name='uq_study_active_slot'))
    op.create_table('study_attempts',*common(),sa.Column('plan_id',sa.String(36),sa.ForeignKey('study_plans.id',ondelete='CASCADE'),nullable=False),sa.Column('lesson_id',sa.String(60),nullable=False),sa.Column('date',sa.Date(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('result',sa.JSON(),nullable=False),sa.Column('passed',sa.Boolean(),nullable=False),sa.UniqueConstraint('user_id','create_key',name='uq_study_attempt_key'))
    op.create_table('study_reviews',*common(),sa.Column('course_id',sa.String(40),nullable=False),sa.Column('version',sa.String(20),nullable=False),sa.Column('card_id',sa.String(80),nullable=False),sa.Column('rating',sa.String(20),nullable=False),sa.Column('streak',sa.Integer(),nullable=False),sa.Column('date',sa.Date(),nullable=False),sa.Column('due_date',sa.Date(),nullable=False),sa.UniqueConstraint('user_id','create_key',name='uq_study_review_key'))
    for table in ('study_plans','study_attempts','study_reviews'):
        op.create_index('ix_'+table+'_user_id',table,['user_id'])
    op.create_index('ix_study_attempts_plan_id','study_attempts',['plan_id'])


def downgrade():
    op.drop_index('ix_study_attempts_plan_id',table_name='study_attempts')
    for table in ('study_reviews','study_attempts','study_plans'):
        op.drop_index('ix_'+table+'_user_id',table_name=table)
        op.drop_table(table)
