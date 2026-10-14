"""add hidden spheres

Revision ID: 4b22f469c5f8
Revises: 69bc28f08523
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b22f469c5f8"
down_revision: Union[str, None] = "69bc28f08523"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("hidden_spheres", sa.JSON(), server_default="[]", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "hidden_spheres")
