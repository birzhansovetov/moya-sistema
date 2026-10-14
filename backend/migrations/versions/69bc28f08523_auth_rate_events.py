"""auth rate events

Revision ID: 69bc28f08523
Revises: 5410d4e6a2b0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "69bc28f08523"
down_revision: Union[str, None] = "5410d4e6a2b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_rate_events_lookup", "auth_rate_events", ["action", "key_hash", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_rate_events_lookup", table_name="auth_rate_events")
    op.drop_table("auth_rate_events")
