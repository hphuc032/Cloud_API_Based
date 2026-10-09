from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import settings
from app.database.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])


def require_legacy_release():
    if settings.AUTH_MODE != "legacy":
        raise HTTPException(status_code=410, detail="Browser authentication is managed by the identity provider")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32)


def _role_value(role: UserRole) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _create_user_access_token(user: User) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "role": _role_value(user.role),
        }
    )


def _is_weak_password(password: str) -> bool:
    return password.isalpha() or password.isdigit()


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_legacy_release)])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new customer account."""
    if _is_weak_password(payload.password):
        raise HTTPException(status_code=400, detail="Password is too weak")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.customer,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Registration successful", "user_id": str(user.id)}


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(require_legacy_release)])
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 password flow.
    Security:
    - Generic login error to reduce user enumeration.
    - Account lockout after repeated failures.
    - Short-lived access token and hashed refresh token.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise auth_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    now = datetime.now(timezone.utc)
    locked_until = user.locked_until

    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    if locked_until and locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked",
        )

    if not verify_password(form_data.password, user.hashed_password):
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)

        db.commit()
        raise auth_error

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = request.client.host if request.client else None

    access_token = _create_user_access_token(user)

    raw_refresh = generate_refresh_token()
    refresh_token_obj = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        ip_address=user.last_login_ip,
        device_info=request.headers.get("User-Agent", "")[:255],
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    db.add(refresh_token_obj)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=raw_refresh,
    )


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_legacy_release)])
def refresh_token(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Rotate refresh token.
    Old token is revoked and a new refresh token is issued.
    """
    token_hash = hash_refresh_token(payload.refresh_token)
    token_obj = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not token_obj or not token_obj.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.query(User).filter(
        User.id == token_obj.user_id,
        User.is_active == True,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    now = datetime.now(timezone.utc)

    token_obj.revoked = True
    token_obj.revoked_at = now

    access_token = _create_user_access_token(user)
    raw_refresh = generate_refresh_token()

    new_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        ip_address=request.client.host if request.client else None,
        device_info=request.headers.get("User-Agent", "")[:255],
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    db.add(new_token)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=raw_refresh,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_legacy_release)])
def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Revoke refresh token on logout."""
    token_hash = hash_refresh_token(payload.refresh_token)
    token_obj = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.user_id == current_user.id,
    ).first()

    if token_obj:
        token_obj.revoked = True
        token_obj.revoked_at = datetime.now(timezone.utc)
        db.commit()


@router.get("/me")
def get_me(current_user: User = Depends(get_current_active_user)):
    """Return current user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": _role_value(current_user.role),
        "is_verified": current_user.is_verified,
    }
