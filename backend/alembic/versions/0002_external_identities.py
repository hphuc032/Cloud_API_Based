"""P3 additive, operator-reviewed external identity bindings; no account linking."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "0002_external_identities"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("external_identities",
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=False),
        sa.Column("review_reference", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("issuer", "subject"),
        sa.UniqueConstraint("issuer", "user_id", name="uq_external_identity_issuer_user"),
        sa.CheckConstraint("issuer LIKE 'https://%' AND length(subject)>0 AND length(reviewed_by)>0 AND length(review_reference)>0", name="ck_external_identity_review"))

def downgrade():
    op.drop_table("external_identities")
