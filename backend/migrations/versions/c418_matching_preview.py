"""Persist opaque matching previews and idempotent start results."""

from alembic import op
import sqlalchemy as sa

revision = "c418_matching_preview"
down_revision = "c417_content_revocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("matching_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("survey_version", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("answers_digest", sa.String(64), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("areas", sa.JSON(), nullable=False),
        sa.Column("expected_active", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "nonce_hash", name="uq_matching_preview_nonce"))
    op.create_index("ix_matching_previews_user_id", "matching_previews", ["user_id"])
    op.create_table("matching_start_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "nonce_hash", name="uq_matching_start_nonce"))
    op.create_index("ix_matching_start_results_user_id", "matching_start_results", ["user_id"])
    op.create_index("ix_matching_start_results_nonce_hash", "matching_start_results", ["nonce_hash"])


def downgrade() -> None:
    op.drop_index("ix_matching_start_results_nonce_hash", table_name="matching_start_results")
    op.drop_index("ix_matching_start_results_user_id", table_name="matching_start_results")
    op.drop_table("matching_start_results")
    op.drop_index("ix_matching_previews_user_id", table_name="matching_previews")
    op.drop_table("matching_previews")
