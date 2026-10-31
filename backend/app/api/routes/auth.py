from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.auth import (
    AuthSuccessResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.users import CurrentUserResponse, UserOrgMembershipDetail
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
    )


@router.post("/register", response_model=AuthSuccessResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Register a new user and organization in a single transaction.
    The registering user is assigned the 'owner' role.
    """
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    user, org, role, access_token, raw_refresh = AuthService.register_user(
        db=db,
        data=data,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    _set_refresh_cookie(response, raw_refresh)

    return AuthSuccessResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=org.id,
        organization_name=org.name,
        role=role,
    )


@router.post("/login", response_model=AuthSuccessResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate user with email and password, returning JWT access token
    and setting an HttpOnly refresh cookie.
    """
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    user, org, role, access_token, raw_refresh = AuthService.login_user(
        db=db,
        data=data,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    _set_refresh_cookie(response, raw_refresh)

    return AuthSuccessResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=org.id if org else None,
        organization_name=org.name if org else None,
        role=role,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    sentinel_refresh_token: Optional[str] = Cookie(None, alias=settings.COOKIE_NAME),
    x_refresh_token: Optional[str] = Header(None, alias="X-Refresh-Token"),
):
    """
    Rotate refresh token and issue new access token.
    Accepts refresh token via HttpOnly cookie (preferred) or X-Refresh-Token header.
    """
    token_candidate = sentinel_refresh_token or x_refresh_token
    if not token_candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from request",
        )

    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    new_access, new_refresh = AuthService.rotate_refresh_token(
        db=db,
        raw_token=token_candidate,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    _set_refresh_cookie(response, new_refresh)

    return TokenResponse(
        access_token=new_access,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    sentinel_refresh_token: Optional[str] = Cookie(None, alias=settings.COOKIE_NAME),
    x_refresh_token: Optional[str] = Header(None, alias="X-Refresh-Token"),
):
    """
    Log out user: revoke refresh token and clear HttpOnly cookie.
    """
    token_candidate = sentinel_refresh_token or x_refresh_token
    if token_candidate:
        AuthService.revoke_refresh_token(db=db, raw_token=token_candidate)

    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve current authenticated user's profile and active organization memberships.
    """
    stmt = (
        select(OrganizationMember)
        .options(joinedload(OrganizationMember.organization))
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(OrganizationMember.created_at.asc())
    )
    memberships = db.scalars(stmt).all()

    org_details = [
        UserOrgMembershipDetail(
            organization_id=m.organization.id,
            organization_name=m.organization.name,
            organization_slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
    ]

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        organizations=org_details,
    )
