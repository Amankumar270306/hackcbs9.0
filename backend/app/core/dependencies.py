import uuid
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.database.models.identity import Organization, OrganizationMember, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT access token and return active User instance."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    user = db.scalars(stmt).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user


def get_current_membership(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    """
    Ensure the current user belongs to the target organization.
    Returns 404 if the organization does not exist or user is not a member,
    preventing organization enumeration.
    """
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == current_user.id,
    )
    membership = db.scalars(stmt).first()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return membership


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    RBAC dependency factory.
    Enforces that the user has one of the allowed roles within the organization.
    """
    def role_checker(
        membership: OrganizationMember = Depends(get_current_membership),
    ) -> OrganizationMember:
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of the following roles: {', '.join(allowed_roles)}",
            )
        return membership

    return role_checker

