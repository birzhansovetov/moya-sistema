"""nutrition profile menu and journals

Revision ID: 6e9a3e77b920
Revises: 0fd56b2d7c6a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6e9a3e77b920"
down_revision: Union[str, None] = "0fd56b2d7c6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("nutrition_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("answers", sa.JSON(), nullable=False), sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("estimate_snapshot", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("nutrition_menus",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_key", sa.String(8), nullable=True), sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("days_snapshot", sa.JSON(), nullable=False), sa.Column("profile_snapshot", sa.JSON(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "active_key", name="uq_nutrition_active_menu"))
    op.create_index("ix_nutrition_menus_user_id", "nutrition_menus", ["user_id"])
    op.create_table("food_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("create_key", sa.String(100), nullable=False), sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("recipe_id", sa.String(80), nullable=False), sa.Column("portions", sa.Float(), nullable=False),
        sa.Column("recipe_snapshot", sa.JSON(), nullable=False), sa.Column("nutrition_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "create_key", name="uq_food_log_create_key"))
    op.create_index("ix_food_logs_user_id", "food_logs", ["user_id"])
    op.create_table("weight_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False), sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "log_date", name="uq_weight_log_date"))
    op.create_index("ix_weight_logs_user_id", "weight_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_weight_logs_user_id", table_name="weight_logs")
    op.drop_table("weight_logs")
    op.drop_index("ix_food_logs_user_id", table_name="food_logs")
    op.drop_table("food_logs")
    op.drop_index("ix_nutrition_menus_user_id", table_name="nutrition_menus")
    op.drop_table("nutrition_menus")
    op.drop_table("nutrition_profiles")
