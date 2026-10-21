from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_admin
from app.database.session import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/users", tags=["Users"])


class UserUpdateAdmin(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

    @field_validator('role','is_active','is_verified', mode='before')
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError('This field cannot be null; omit it to leave it unchanged')
        return value


def _role_value(role: UserRole) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _public_user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": _role_value(user.role),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.get("/")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: list all users."""
    total = db.query(User).count()
    users = db.query(User).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [_public_user_response(u) for u in users],
    }


@router.get("/{user_id}")
def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get user detail.
    Security: users can only view their own profile unless admin.
    """
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = _public_user_response(user)
    data["phone"] = user.phone
    data["created_at"] = user.created_at.isoformat()

    return data


@router.patch("/{user_id}")
def update_user_admin(
    user_id: UUID,
    payload: UserUpdateAdmin,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: update user role/status."""
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        if "role" in update_data and update_data["role"] != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot remove own admin role",
            )

        if update_data.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot deactivate own account",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()

    return {"message": "User updated"}
