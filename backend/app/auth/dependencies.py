from app.middleware.logging import mark
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.external_identity import ExternalIdentity
from app.config import settings
from app.auth.oidc import decode_oidc_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validate JWT and return current user.
    Raises 401 if token is invalid/expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_exception
    token = credentials.credentials
    try:
        if settings.AUTH_MODE == "oidc":
            payload = decode_oidc_access_token(token)
            user = (db.query(User).join(ExternalIdentity, ExternalIdentity.user_id == User.id)
                    .filter(ExternalIdentity.issuer == settings.OIDC_ISSUER,
                            ExternalIdentity.subject == payload["sub"], User.is_active == True).first())
            if user is None:
                mark("identity_unmapped_or_disabled")
                raise credentials_exception
            return user
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


def require_role(*roles: UserRole):
    """
    Factory dependency: enforce RBAC.
    Usage: Depends(require_role(UserRole.admin, UserRole.staff))
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            mark("rbac_denied")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


# Shorthand dependencies
require_admin = require_role(UserRole.admin)
require_staff_or_admin = require_role(UserRole.admin, UserRole.staff)
