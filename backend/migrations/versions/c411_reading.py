"""Private books and reading history."""
from alembic import op
import sqlalchemy as sa
revision='c411_reading'
down_revision='c410_personal'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('reading_books',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('title',sa.String(200),nullable=False),sa.Column('author',sa.String(160),nullable=False),
        sa.Column('pages',sa.Integer(),nullable=False),sa.Column('initial_page',sa.Integer(),nullable=False),
        sa.Column('daily_pages',sa.Integer(),nullable=False),sa.Column('status',sa.String(12),nullable=False),
        sa.Column('start_date',sa.Date(),nullable=True),sa.Column('end_date',sa.Date(),nullable=True),
        sa.Column('cover_url',sa.String(2000),nullable=False),sa.Column('final_impression',sa.Text(),nullable=False),
        sa.Column('create_key',sa.String(100),nullable=False),sa.Column('create_fingerprint',sa.String(64),nullable=False),
        sa.Column('deleted_at',sa.DateTime(),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','create_key',name='uq_reading_book_key'))
    op.create_index('ix_reading_books_user_id','reading_books',['user_id'])
    op.create_table('reading_logs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('book_id',sa.String(36),sa.ForeignKey('reading_books.id',ondelete='CASCADE'),nullable=False),
        sa.Column('date',sa.Date(),nullable=False),sa.Column('page',sa.Integer(),nullable=True),
        sa.Column('chapter',sa.String(200),nullable=False),sa.Column('text',sa.Text(),nullable=False),
        sa.Column('reflection',sa.JSON(),nullable=False),sa.Column('search_text',sa.Text(),nullable=False),
        sa.Column('create_key',sa.String(100),nullable=False),sa.Column('create_fingerprint',sa.String(64),nullable=False),
        sa.Column('deleted_at',sa.DateTime(),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('book_id','create_key',name='uq_reading_log_key'))
    op.create_index('ix_reading_logs_book_id','reading_logs',['book_id'])


def downgrade():
    op.drop_index('ix_reading_logs_book_id',table_name='reading_logs');op.drop_table('reading_logs')
    op.drop_index('ix_reading_books_user_id',table_name='reading_books');op.drop_table('reading_books')
