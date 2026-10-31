"""API routes for Report Generator (Milestone 8)."""

from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database.connection import get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.reports import (
    ReportCreateRequest,
    ReportListResponse,
    ReportReadinessCheck,
    ReportResponse,
    ReportStructuredPreviewResponse,
)
from app.services.report_service import ReportService

router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}/reports",
    tags=["Report Generator"],
)


@router.get("/readiness", response_model=ReportReadinessCheck)
def check_report_readiness(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Evaluate pre-flight report generation readiness."""
    return ReportService.check_readiness(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
    )


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def generate_report(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    data: ReportCreateRequest,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger complete report generation from Adjudicator consensus outputs and compile PDF."""
    return ReportService.generate_report(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        user_id=current_user.id,
        data=data,
    )


@router.get("", response_model=ReportListResponse)
def list_reports(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List all generated report versions for an audit case."""
    reports = ReportService.list_reports(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
    )
    return ReportListResponse(items=reports, total=len(reports))


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    report_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Retrieve metadata and status of a specific generated report."""
    report = ReportService.get_report(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        report_id=report_id,
    )
    return ReportResponse.model_validate(report)


@router.get("/{report_id}/download")
def download_report(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    report_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Download the verified compliance audit report PDF."""
    abs_path, download_filename = ReportService.get_report_file_path(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        report_id=report_id,
    )
    return FileResponse(
        path=abs_path,
        media_type="application/pdf",
        filename=download_filename,
    )


@router.get("/{report_id}/preview", response_model=ReportStructuredPreviewResponse)
def get_report_preview(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    report_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Retrieve structured 12-section report data for high-fidelity interactive browser preview."""
    report = ReportService.get_report(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        report_id=report_id,
    )
    return ReportStructuredPreviewResponse(
        report_id=report.id,
        title=report.title,
        version=report.version,
        format=report.format,
        generation_status=report.generation_status,
        created_at=report.created_at,
        is_stale=report.is_stale,
        data=report.report_metadata,
    )

