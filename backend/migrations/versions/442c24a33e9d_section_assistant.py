"""Metadata-only section assistant; server access only."""
from alembic import op
import sqlalchemy as sa
revision='442c24a33e9d'
down_revision='c426_uploaded_books'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('assistant_requests',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('section',sa.String(24),nullable=False),sa.Column('topic_id',sa.String(60),nullable=False),
        sa.Column('material_kind',sa.String(24)),sa.Column('material_id',sa.String(120)),sa.Column('material_version',sa.String(40)),
        sa.Column('source',sa.String(20),nullable=False),sa.Column('prompt_version',sa.String(30),nullable=False),
        sa.Column('model',sa.String(120),nullable=False),sa.Column('latency_ms',sa.Integer(),nullable=False),
        sa.Column('helped',sa.Boolean()),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_assistant_requests_user_id','assistant_requests',['user_id'])
    op.create_index('ix_assistant_requests_created_at','assistant_requests',['created_at'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE assistant_requests ENABLE ROW LEVEL SECURITY')
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON assistant_requests FROM anon; END IF; IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON assistant_requests FROM authenticated; END IF; END $$")

def downgrade():
    op.drop_index('ix_assistant_requests_created_at',table_name='assistant_requests')
    op.drop_index('ix_assistant_requests_user_id',table_name='assistant_requests')
    op.drop_table('assistant_requests')
