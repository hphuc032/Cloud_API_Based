"""Inactive P3 mapping metadata; existing auth never queries this model."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.database.session import Base

class ExternalIdentity(Base):
    __tablename__ = 'external_identities'
    issuer = Column(String(512), primary_key=True)
    subject = Column(String(255), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reviewed_by = Column(String(255), nullable=False)
    review_reference = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('issuer', 'user_id', name='uq_external_identity_issuer_user'),
        CheckConstraint("issuer LIKE 'https://%' AND length(subject)>0 AND length(reviewed_by)>0 AND length(review_reference)>0", name='ck_external_identity_review'),
    )
