"""One-time markers for confirmed backup restores."""

from alembic import op
import sqlalchemy as sa

revision = "c414_backup"
down_revision = "c413_study_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backup_uses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_backup_uses_user_id", "backup_uses", ["user_id"])


def downgrade():
    op.drop_index("ix_backup_uses_user_id", table_name="backup_uses")
    op.drop_table("backup_uses")
