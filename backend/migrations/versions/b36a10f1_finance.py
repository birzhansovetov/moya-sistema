"""Private expense tracking.

Revision ID: b36a10f1
Revises: 6e9a3e77b920
"""
from alembic import op
import sqlalchemy as sa

revision = "b36a10f1"
down_revision = "6e9a3e77b920"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("finance_currency", sa.String(3), nullable=False, server_default="KZT"))
    op.create_table("expense_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False), sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "name_key", name="uq_expense_category_name"))
    op.create_index("ix_expense_categories_user_id", "expense_categories", ["user_id"])
    op.create_table("expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("expense_categories.id"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False), sa.Column("note", sa.String(500), nullable=False),
        sa.Column("note_search", sa.String(1000), nullable=False), sa.Column("create_key", sa.String(100), nullable=False),
        sa.Column("create_fingerprint", sa.String(64), nullable=False), sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "create_key", name="uq_expense_create_key"))
    op.create_index("ix_expenses_scope_date", "expenses", ["user_id", "currency", "expense_date"])


def downgrade():
    op.drop_index("ix_expenses_scope_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_expense_categories_user_id", table_name="expense_categories")
    op.drop_table("expense_categories")
    op.drop_column("users", "finance_currency")
