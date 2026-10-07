from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.auth.dependencies import require_staff_or_admin
from app.database.session import get_db
from app.models.product import Category, Product
from app.models.user import User

router = APIRouter(prefix="/products", tags=["Products"])


class ProductCreate(BaseModel):
    category_id: Optional[UUID] = None
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: float = Field(..., gt=0)
    stock_quantity: int = Field(0, ge=0)
    image_url: Optional[HttpUrl] = None


class ProductUpdate(BaseModel):
    category_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[float] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    image_url: Optional[HttpUrl] = None


def _ensure_category_exists(db: Session, category_id: Optional[UUID]) -> None:
    if category_id is None:
        return

    category = db.query(Category).filter(
        Category.id == category_id,
        Category.is_active == True,
    ).first()

    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")


def _product_response(product: Product) -> dict:
    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": float(product.price),
        "stock_quantity": product.stock_quantity,
        "image_url": product.image_url,
        "category_id": str(product.category_id) if product.category_id else None,
        "created_at": product.created_at.isoformat(),
    }


@router.get("/")
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    """Public: list active products with pagination."""
    query = db.query(Product).filter(Product.is_active == True)

    if category_id:
        query = query.filter(Product.category_id == category_id)

    total = query.count()
    products = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_product_response(p) for p in products],
    }


@router.get("/{product_id}")
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    """Public: get single product detail."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_active == True,
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return _product_response(product)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Staff/Admin: create a new product."""
    _ensure_category_exists(db, payload.category_id)

    if db.query(Product).filter(Product.sku == payload.sku).first():
        raise HTTPException(status_code=400, detail="SKU already exists")

    data = payload.model_dump()
    if data.get("image_url") is not None:
        data["image_url"] = str(data["image_url"])

    product = Product(
        **data,
        created_by=current_user.id,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return {"id": str(product.id), "message": "Product created"}


@router.patch("/{product_id}")
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Staff/Admin: update product fields."""
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "category_id" in update_data:
        _ensure_category_exists(db, update_data["category_id"])

    if update_data.get("image_url") is not None:
        update_data["image_url"] = str(update_data["image_url"])

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()

    return {"message": "Product updated"}


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    current_user: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """Staff/Admin: soft-delete product."""
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    db.commit()