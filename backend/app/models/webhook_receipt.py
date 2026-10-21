from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.database.session import Base

class WebhookReceipt(Base):
    __tablename__ = 'webhook_receipts'
    provider = Column(String(128), primary_key=True)
    event_id = Column(String(256), primary_key=True)
    payload_sha256 = Column(String(64), nullable=False)
    response = Column(JSONB, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
