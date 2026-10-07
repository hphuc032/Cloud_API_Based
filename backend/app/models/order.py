import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_number = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(
        SAEnum(OrderStatus),
        nullable=False,
        default=OrderStatus.pending,
        index=True,
    )
    total_amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="VND")

    shipping_name = Column(String(255))
    shipping_phone = Column(String(20))
    shipping_address = Column(Text)
    shipping_city = Column(String(100))

    notes = Column(Text)
    cancelled_at = Column(DateTime(timezone=True))
    cancel_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = relationship("User", back_populates="orders")
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Order id={self.id} order_number={self.order_number} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __repr__(self):
        return f"<OrderItem order_id={self.order_id} product_id={self.product_id} qty={self.quantity}>"