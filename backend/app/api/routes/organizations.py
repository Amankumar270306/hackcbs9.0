from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.members import MemberAddRequest, MemberResponse, MemberRoleUpdate
from app.schemas.organizations import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all organizations that the current authenticated user belongs to."""
    return OrganizationService.list_user_organizations(db=db, user_id=current_user.id)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new organization and assign the current user as owner."""
    return OrganizationService.create_organization(db=db, user=current_user, data=data)


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Get details of a specific organization if the user is a member."""
    return OrganizationService.get_organization_detail(
        db=db,
        organization_id=organization_id,
        user_role=membership.role,
    )


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin"])),
    db: Session = Depends(get_db),
):
    """Update organization details (owners and admins only)."""
    return OrganizationService.update_organization(
        db=db,
        organization_id=organization_id,
        data=data,
    )


# Member Management
@router.get("/{organization_id}/members", response_model=List[MemberResponse])
def list_members(
    organization_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List all members and their roles in the organization."""
    return OrganizationService.list_members(db=db, organization_id=organization_id)


@router.post("/{organization_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    organization_id: uuid.UUID,
    data: MemberAddRequest,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin"])),
    db: Session = Depends(get_db),
):
    """Add an existing registered user to the organization."""
    return OrganizationService.add_member(
        db=db,
        organization_id=organization_id,
        data=data,
        actor_role=membership.role,
    )


@router.patch("/{organization_id}/members/{user_id}", response_model=MemberResponse)
def update_member_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MemberRoleUpdate,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the role of an organization member."""
    return OrganizationService.update_member_role(
        db=db,
        organization_id=organization_id,
        target_user_id=user_id,
        data=data,
        actor_id=current_user.id,
        actor_role=membership.role,
    )


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a member from the organization."""
    OrganizationService.remove_member(
        db=db,
        organization_id=organization_id,
        target_user_id=user_id,
        actor_id=current_user.id,
        actor_role=membership.role,
    )
