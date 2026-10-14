"""task create fingerprint

Revision ID: 5410d4e6a2b0
Revises: ebf02ab109a8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5410d4e6a2b0"
down_revision: Union[str, None] = "ebf02ab109a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("create_fingerprint", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "create_fingerprint")
