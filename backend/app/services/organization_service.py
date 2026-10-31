from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.identity import Organization, OrganizationMember, User
from app.schemas.members import MemberAddRequest, MemberResponse, MemberRoleUpdate
from app.schemas.organizations import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from app.services.auth_service import generate_unique_slug


class OrganizationService:
    @staticmethod
    def list_user_organizations(db: Session, user_id: uuid.UUID) -> List[OrganizationResponse]:
        """List all organizations that a user belongs to, including the user's role."""
        stmt = (
            select(OrganizationMember)
            .options(joinedload(OrganizationMember.organization))
            .where(OrganizationMember.user_id == user_id)
            .order_by(OrganizationMember.created_at.asc())
        )
        memberships = db.scalars(stmt).all()

        results = []
        for m in memberships:
            org = m.organization
            results.append(
                OrganizationResponse(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    created_at=org.created_at,
                    role=m.role,
                )
            )
        return results

    @staticmethod
    def create_organization(
        db: Session,
        user: User,
        data: OrganizationCreate,
    ) -> OrganizationResponse:
        """Create a new organization and make the requesting user its owner."""
        slug = generate_unique_slug(db, data.name)
        org = Organization(
            name=data.name.strip(),
            slug=slug,
        )
        db.add(org)
        db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
        db.add(member)
        db.commit()
        db.refresh(org)

        return OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
            role="owner",
        )

    @staticmethod
    def get_organization_detail(
        db: Session,
        organization_id: uuid.UUID,
        user_role: Optional[str] = None,
    ) -> OrganizationResponse:
        """Get organization details."""
        org = db.get(Organization, organization_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        return OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
            role=user_role,
        )

    @staticmethod
    def update_organization(
        db: Session,
        organization_id: uuid.UUID,
        data: OrganizationUpdate,
    ) -> OrganizationResponse:
        """Update organization details (name, etc.)."""
        org = db.get(Organization, organization_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        if data.name:
            org.name = data.name.strip()
        db.commit()
        db.refresh(org)
        return OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
        )

    @staticmethod
    def list_members(db: Session, organization_id: uuid.UUID) -> List[MemberResponse]:
        """List all members of an organization with user profile details."""
        stmt = (
            select(OrganizationMember)
            .options(joinedload(OrganizationMember.user))
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.created_at.asc())
        )
        members = db.scalars(stmt).all()

        results = []
        for m in members:
            results.append(
                MemberResponse(
                    id=m.id,
                    organization_id=m.organization_id,
                    user_id=m.user_id,
                    email=m.user.email,
                    full_name=m.user.full_name,
                    role=m.role,
                    created_at=m.created_at,
                )
            )
        return results

    @staticmethod
    def add_member(
        db: Session,
        organization_id: uuid.UUID,
        data: MemberAddRequest,
        actor_role: str,
    ) -> MemberResponse:
        """Add an existing user to an organization."""
        target_email = data.email.strip().lower()
        stmt = select(User).where(User.email == target_email)
        target_user = db.scalars(stmt).first()

        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No registered user found with email '{data.email}'",
            )

        # Check existing membership
        mem_stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == target_user.id,
        )
        if db.scalars(mem_stmt).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization",
            )

        # Only owners can add someone directly as owner
        if data.role == "owner" and actor_role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization owners can assign the owner role",
            )

        member = OrganizationMember(
            organization_id=organization_id,
            user_id=target_user.id,
            role=data.role,
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        return MemberResponse(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=member.role,
            created_at=member.created_at,
        )

    @staticmethod
    def update_member_role(
        db: Session,
        organization_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: MemberRoleUpdate,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> MemberResponse:
        """Update role of an organization member."""
        mem_stmt = (
            select(OrganizationMember)
            .options(joinedload(OrganizationMember.user))
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == target_user_id,
            )
        )
        membership = db.scalars(mem_stmt).first()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this organization",
            )

        new_role = data.role

        # Rule 1: Admins cannot promote themselves to owner
        if actor_id == target_user_id and actor_role == "admin" and new_role == "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot promote themselves to owner",
            )

        # Rule 2: Only owners can assign or remove owner role
        if (new_role == "owner" or membership.role == "owner") and actor_role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization owners can assign or demote the owner role",
            )

        # Rule 3: Cannot demote the last owner
        if membership.role == "owner" and new_role != "owner":
            owner_count_stmt = (
                select(func.count())
                .select_from(OrganizationMember)
                .where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.role == "owner",
                )
            )
            owner_count = db.scalar(owner_count_stmt)
            if owner_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last owner. Designate another owner first.",
                )

        membership.role = new_role
        db.commit()
        db.refresh(membership)

        return MemberResponse(
            id=membership.id,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            email=membership.user.email,
            full_name=membership.user.full_name,
            role=membership.role,
            created_at=membership.created_at,
        )

    @staticmethod
    def remove_member(
        db: Session,
        organization_id: uuid.UUID,
        target_user_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> None:
        """Remove a member from an organization."""
        mem_stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == target_user_id,
        )
        membership = db.scalars(mem_stmt).first()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this organization",
            )

        # Rule 1: Check if target is owner
        if membership.role == "owner":
            # Count owners
            owner_count_stmt = (
                select(func.count())
                .select_from(OrganizationMember)
                .where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.role == "owner",
                )
            )
            owner_count = db.scalar(owner_count_stmt)
            if owner_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove the last owner of the organization",
                )

            # Only owners can remove other owners
            if actor_role != "owner" and actor_id != target_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization owners can remove an owner",
                )

        db.delete(membership)
        db.commit()
