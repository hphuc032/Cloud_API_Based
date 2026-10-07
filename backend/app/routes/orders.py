from uuid import UUID
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_active_user, require_staff_or_admin
from app.database.session import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User, UserRole

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Schemas ───────────────────────────────────────────────────
class OrderItemIn(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, le=100)


class OrderCreate(BaseModel):
    items: List[OrderItemIn] = Field(..., min_length=1, max_length=50)
    shipping_name: Optional[str] = Field(None, max_length=100)
    shipping_phone: Optional[str] = Field(None, max_length=20)
    shipping_address: Optional[str] = Field(None, max_length=255)
    shipping_city: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    cancel_reason: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────
def _generate_order_number() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    import secrets
    return f"ORD-{ts}-{secrets.token_hex(3).upper()}"


# ── Endpoints ─────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Customer: place a new order.
    Security: BOLA protection — order is always linked to current_user.id,
    never from request body.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    total = 0.0
    order_items = []

    for item_in in payload.items:
        product = db.query(Product).filter(
            Product.id == item_in.product_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_in.product_id} not found")
        if product.stock_quantity < item_in.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

        unit_price = float(product.price)
        total += unit_price * item_in.quantity
        order_items.append(
            OrderItem(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
            )
        )
        # Deduct stock
        product.stock_quantity -= item_in.quantity

    order = Order(
        user_id=current_user.id,        # ← Always server-side, never trust client
        order_number=_generate_order_number(),
        total_amount=round(total, 2),
        shipping_name=payload.shipping_name,
        shipping_phone=payload.shipping_phone,
        shipping_address=payload.shipping_address,
        shipping_city=payload.shipping_city,
        notes=payload.notes,
        order_items=order_items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {"id": str(order.id), "order_number": order.order_number, "total_amount": order.total_amount}


@router.get("/")
def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List orders.
    Security (BOLA): customers see only their own orders;
    admin/staff can see all.
    """
    query = db.query(Order)
    if current_user.role == UserRole.customer:
        query = query.filter(Order.user_id == current_user.id)

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": float(o.total_amount),
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


@router.get("/{order_id}")
def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get order detail.
    Security (BOLA): enforce object-level ownership check.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # BOLA check: customers can only view their own orders
    if current_user.role == UserRole.customer and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "currency": order.currency,
        "shipping": {
            "name": order.shipping_name,
            "phone": order.shipping_phone,
            "address": order.shipping_address,
            "city": order.shipping_city,
        },
        "items": [
            {
                "product_id": str(i.product_id),
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "subtotal": float(i.subtotal),
            }
            for i in order.order_items
        ],
        "created_at": order.created_at.isoformat(),
    }


@router.patch("/{order_id}/status")
def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Staff/Admin: update order status."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = payload.status
    if payload.status == OrderStatus.cancelled:
        order.cancelled_at = datetime.utcnow()
        order.cancel_reason = payload.cancel_reason

    db.commit()
    return {"message": f"Order status updated to {payload.status}"}