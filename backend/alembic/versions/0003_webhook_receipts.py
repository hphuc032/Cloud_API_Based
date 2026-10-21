"""P5 additive, atomic acknowledgements; existing IDs and identity bindings untouched."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0003_webhook_receipts'
down_revision = '0002_external_identities'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('webhook_receipts',
        sa.Column('provider', sa.String(128), nullable=False),
        sa.Column('event_id', sa.String(256), nullable=False),
        sa.Column('payload_sha256', sa.String(64), nullable=False),
        sa.Column('response', JSONB, nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('provider','event_id'),
        sa.CheckConstraint("length(provider)>0 AND length(event_id)>0 AND payload_sha256 ~ '^[0-9a-f]{64}$'", name='ck_webhook_receipt_identity'))

def downgrade():
    op.drop_table('webhook_receipts')
