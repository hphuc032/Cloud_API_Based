from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database.session import Base


class AuditLog(Base):
    """
    Security audit trail — immutable write-once table.
    Supports MTTD (Mean Time to Detect) and incident response.
    """
    __tablename__ = "audit_logs"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action        = Column(String(100), nullable=False, index=True)   # e.g. LOGIN, CREATE_ORDER
    resource_type = Column(String(50), index=True)
    resource_id   = Column(UUID(as_uuid=True), index=True)
    ip_address    = Column(String(45))
    user_agent    = Column(String(500))
    request_id    = Column(UUID(as_uuid=True))                        # Correlation ID
    status_code   = Column(Integer)
    detail        = Column(JSONB)                                     # Flexible extra data
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # Relationship
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action} user_id={self.user_id}>"