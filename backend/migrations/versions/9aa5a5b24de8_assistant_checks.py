"""assistant_checks

Revision ID: 9aa5a5b24de8
Revises: 442c24a33e9d
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9aa5a5b24de8'
down_revision: Union[str, None] = '442c24a33e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table('assistant_check_attempts',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('issue_id',sa.String(36),nullable=False),
        sa.Column('check_id',sa.String(160),nullable=False),
        sa.Column('check_version',sa.String(40),nullable=False),
        sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('material',sa.JSON(),nullable=False),
        sa.Column('option_id',sa.String(40),nullable=False),
        sa.Column('correct',sa.Boolean(),nullable=False),
        sa.Column('activity',sa.JSON()),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','issue_id',name='uq_assistant_check_issue'))
    op.create_index('ix_assistant_check_attempts_user_id','assistant_check_attempts',['user_id'])
    op.create_index('ix_assistant_check_attempts_created_at','assistant_check_attempts',['created_at'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE assistant_check_attempts ENABLE ROW LEVEL SECURITY')
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON assistant_check_attempts FROM anon; END IF; IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON assistant_check_attempts FROM authenticated; END IF; END $$")


def downgrade():
    op.drop_table('assistant_check_attempts')
