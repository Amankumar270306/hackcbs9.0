from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.audit_runs import AuditRunCreate, AuditRunResponse
from app.schemas.audits import AuditCreate, AuditListResponse, AuditResponse, AuditUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/organizations/{organization_id}/audits", tags=["Audits"])


@router.post("", response_model=AuditResponse, status_code=status.HTTP_201_CREATED)
def create_audit(
    organization_id: uuid.UUID,
    data: AuditCreate,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new compliance audit case."""
    return AuditService.create_audit(
        db=db,
        organization_id=organization_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=AuditListResponse)
def list_audits(
    organization_id: uuid.UUID,
    search: Optional[str] = Query(None, description="Search term for audit title, application or description"),
    status: Optional[str] = Query(None, description="Filter by audit status (draft, active, archived, completed, or all)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List audits for an organization with pagination, filtering, and summary metrics."""
    items, total = AuditService.list_audits(
        db=db,
        organization_id=organization_id,
        search=search,
        status_filter=status,
        page=page,
        size=size,
    )
    return AuditListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Retrieve details and metrics of a specific audit."""
    return AuditService.get_audit(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
    )


@router.patch("/{audit_id}", response_model=AuditResponse)
def update_audit(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    data: AuditUpdate,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
):
    """Update audit parameters."""
    return AuditService.update_audit(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        data=data,
    )


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_audit(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
):
    """Archive an audit case (soft delete preserving execution history)."""
    AuditService.archive_audit(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
    )


# ---------------- Audit Runs ----------------

@router.post("/{audit_id}/runs", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
def create_audit_run(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    data: AuditRunCreate,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new sequential audit run."""
    return AuditService.create_audit_run(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("/{audit_id}/runs", response_model=List[AuditRunResponse])
def list_audit_runs(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List all execution runs for an audit."""
    return AuditService.list_audit_runs(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
    )


@router.get("/{audit_id}/runs/{run_id}", response_model=AuditRunResponse)
def get_audit_run(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    run_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific audit execution run."""
    return AuditService.get_audit_run(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        run_id=run_id,
    )
