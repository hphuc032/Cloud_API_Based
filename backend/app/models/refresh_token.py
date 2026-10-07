import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.session import Base


class RefreshToken(Base):
    """
    Stores hashed refresh tokens to support revocation.
    Never store raw tokens, only SHA-256 hashes.
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    device_info = Column(String(255))
    ip_address = Column(String(45))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="refresh_tokens")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self._as_utc(self.expires_at)

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    def __repr__(self):
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.revoked}>"