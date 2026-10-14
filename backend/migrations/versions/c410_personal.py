"""Private personal diary and dated events."""
from alembic import op
import sqlalchemy as sa
revision = 'c410_personal'
down_revision = 'b36a10f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('personal_entries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(12), nullable=False), sa.Column('title', sa.String(160), nullable=False),
        sa.Column('body', sa.Text(), nullable=False), sa.Column('date', sa.Date(), nullable=True),
        sa.Column('mood', sa.String(12), nullable=True), sa.Column('activity', sa.String(12), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False), sa.Column('impression', sa.Text(), nullable=False),
        sa.Column('search_text', sa.Text(), nullable=False), sa.Column('create_key', sa.String(100), nullable=False),
        sa.Column('create_fingerprint', sa.String(64), nullable=False), sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id','create_key',name='uq_personal_create_key'))
    op.create_index('ix_personal_entries_user_id','personal_entries',['user_id'])


def downgrade():
    op.drop_index('ix_personal_entries_user_id',table_name='personal_entries')
    op.drop_table('personal_entries')
