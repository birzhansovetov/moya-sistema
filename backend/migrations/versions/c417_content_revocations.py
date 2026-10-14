"""Track active content revocations and append-only operator audit."""

from alembic import op
import sqlalchemy as sa

revision = "c417_content_revocations"
down_revision = "c416_survey_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("content_revocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("item_id", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("kind", "item_id", "version", name="uq_content_revocation_variant"))
    op.create_table("content_revocation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("item_id", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade() -> None:
    op.drop_table("content_revocation_events")
    op.drop_table("content_revocations")
