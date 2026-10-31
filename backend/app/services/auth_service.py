from datetime import datetime, timezone
import re
import secrets
from typing import Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.database.models.auth import RefreshToken
from app.database.models.identity import Organization, OrganizationMember, User
from app.schemas.auth import LoginRequest, RegisterRequest


def generate_unique_slug(db: Session, name: str) -> str:
    """Generate a unique URL-friendly slug for an organization."""
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base_slug:
        base_slug = "org"
    base_slug = base_slug[:80]

    # Check for existing
    slug = base_slug
    counter = 1
    while True:
        stmt = select(func.count()).select_from(Organization).where(Organization.slug == slug)
        exists = db.scalar(stmt)
        if not exists:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


class AuthService:
    @staticmethod
    def register_user(
        db: Session,
        data: RegisterRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, Organization, str, str, str]:
        """
        Register a new user and organization in a single transaction.
        The user is assigned the 'owner' role in the new organization.
        Returns: (user, org, role, access_token, raw_refresh_token)
        """
        email_clean = data.email.strip().lower()

        # Check if email is already taken
        stmt = select(User).where(User.email == email_clean)
        if db.scalars(stmt).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists",
            )

        # Hash password using Argon2id
        hashed_pw = hash_password(data.password)

        # Create user
        user = User(
            email=email_clean,
            hashed_password=hashed_pw,
            full_name=data.full_name.strip(),
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Create organization
        slug = generate_unique_slug(db, data.organization_name)
        org = Organization(
            name=data.organization_name.strip(),
            slug=slug,
        )
        db.add(org)
        db.flush()

        # Create owner membership
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
        db.add(member)
        db.flush()

        # Issue refresh token
        raw_refresh, token_hash, jti, expires_at = generate_refresh_token()
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:100] if ip_address else None,
        )
        db.add(refresh_token_record)
        db.flush()

        # Issue JWT access token
        access_token = create_access_token(
            subject=str(user.id),
            claims={
                "email": user.email,
                "org_id": str(org.id),
                "role": "owner",
            },
        )

        db.commit()
        db.refresh(user)
        db.refresh(org)

        return user, org, "owner", access_token, raw_refresh

    @staticmethod
    def login_user(
        db: Session,
        data: LoginRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, Optional[Organization], Optional[str], str, str]:
        """
        Authenticate user credentials and issue token pair.
        Returns: (user, primary_org, primary_role, access_token, raw_refresh_token)
        """
        email_clean = data.email.strip().lower()
        stmt = select(User).where(User.email == email_clean)
        user = db.scalars(stmt).first()

        if user is None or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive. Please contact your organization administrator.",
            )

        # Find primary organization membership
        mem_stmt = (
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at.asc())
        )
        first_membership = db.scalars(mem_stmt).first()

        primary_org = None
        primary_role = None
        claims = {"email": user.email}

        if first_membership:
            primary_org = db.get(Organization, first_membership.organization_id)
            primary_role = first_membership.role
            claims["org_id"] = str(first_membership.organization_id)
            claims["role"] = primary_role

        # Issue refresh token
        raw_refresh, token_hash, jti, expires_at = generate_refresh_token()
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:100] if ip_address else None,
        )
        db.add(refresh_token_record)
        db.flush()

        # Issue access token
        access_token = create_access_token(
            subject=str(user.id),
            claims=claims,
        )

        db.commit()
        db.refresh(user)

        return user, primary_org, primary_role, access_token, raw_refresh

    @staticmethod
    def rotate_refresh_token(
        db: Session,
        raw_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Rotate refresh token: revoke existing and issue a new pair.
        Returns: (new_access_token, new_raw_refresh_token)
        """
        token_hash = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        record = db.scalars(stmt).first()

        now = datetime.now(timezone.utc)

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if record.revoked_at is not None:
            # Token reuse detected! Revoke all active sessions for this user for security.
            user_tokens_stmt = select(RefreshToken).where(
                RefreshToken.user_id == record.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            for active_token in db.scalars(user_tokens_stmt).all():
                active_token.revoked_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Compromised refresh token reused. All sessions revoked.",
            )

        if record.expires_at <= now:
            record.revoked_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        user = db.get(User, record.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Revoke the old token
        record.revoked_at = now

        # Issue new refresh token
        new_raw, new_hash, new_jti, new_expires = generate_refresh_token()
        new_record = RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            jti=new_jti,
            expires_at=new_expires,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:100] if ip_address else None,
        )
        db.add(new_record)
        db.flush()

        # Issue new access token
        access_token = create_access_token(
            subject=str(user.id),
            claims={"email": user.email},
        )

        db.commit()
        return access_token, new_raw

    @staticmethod
    def revoke_refresh_token(db: Session, raw_token: str) -> None:
        """Revoke a refresh token on logout."""
        token_hash = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        record = db.scalars(stmt).first()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            db.commit()

