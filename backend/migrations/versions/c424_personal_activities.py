"""Keep multiple activities on a diary entry."""

from alembic import op
import sqlalchemy as sa

revision = 'c424_personal_activities'
down_revision = 'c423_finance_income'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('personal_entries', sa.Column('activities', sa.JSON(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text("UPDATE personal_entries SET activities = json_build_array(activity)"))
    else:
        bind.execute(sa.text("UPDATE personal_entries SET activities = json_array(activity)"))


def downgrade() -> None:
    op.drop_column('personal_entries', 'activities')
