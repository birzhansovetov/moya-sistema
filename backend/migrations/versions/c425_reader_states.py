"""Store private reader positions and bookmarks."""

from alembic import op
import sqlalchemy as sa

revision = 'c425_reader_states'
down_revision = 'c424_personal_activities'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('reader_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_id', sa.String(160), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('location', sa.JSON(), nullable=True),
        sa.Column('bookmarks', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'content_id', name='uq_reader_state_owner_content'))
    op.create_index('ix_reader_states_user_id', 'reader_states', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_reader_states_user_id', table_name='reader_states')
    op.drop_table('reader_states')
