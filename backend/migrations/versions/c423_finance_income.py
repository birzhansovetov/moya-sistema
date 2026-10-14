"""Record income alongside expenses."""

from alembic import op
import sqlalchemy as sa

revision = 'c423_finance_income'
down_revision = 'c422_study_assist_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('incomes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('source', sa.String(60), nullable=False),
        sa.Column('income_date', sa.Date(), nullable=False),
        sa.Column('note', sa.String(500), nullable=False),
        sa.Column('create_key', sa.String(100), nullable=False),
        sa.Column('create_fingerprint', sa.String(64), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'create_key', name='uq_income_create_key'))
    op.create_index('ix_incomes_scope_date', 'incomes', ['user_id', 'currency', 'income_date'])


def downgrade() -> None:
    op.drop_index('ix_incomes_scope_date', table_name='incomes')
    op.drop_table('incomes')
