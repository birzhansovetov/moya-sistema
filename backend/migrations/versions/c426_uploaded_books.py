"""Track private files in Neon Object Storage."""

from alembic import op
import sqlalchemy as sa

revision = 'c426_uploaded_books'
down_revision = 'c425_reader_states'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('uploaded_books',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('original_filename', sa.String(200), nullable=False),
        sa.Column('format', sa.String(8), nullable=False),
        sa.Column('object_key', sa.String(200), nullable=False, unique=True),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('create_key', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'create_key', name='uq_uploaded_book_owner_key'))
    op.create_index('ix_uploaded_books_user_id', 'uploaded_books', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_uploaded_books_user_id', table_name='uploaded_books')
    op.drop_table('uploaded_books')
