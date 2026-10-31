"""Regulatory knowledge base, Legal Analyst extraction, and audit mapping API endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import SessionLocal, get_db
from app.database.models.identity import OrganizationMember, User
from app.database.models.regulatory import (
    AuditRequirement,
    RegulatoryDocument,
    RegulatoryDocumentChunk,
    RegulatoryExtractionJob,
    RegulatoryFramework,
    RequirementAuditHistory,
)
from app.database.models.assessments import Requirement
from app.schemas.regulatory import (
    AuditEvidenceSuggestionResponse,
    AuditRequirementMapRequest,
    AuditRequirementResponse,
    AuditRequirementUpdateRequest,
    RegulatoryDocumentChunkResponse,
    RegulatoryDocumentResponse,
    RegulatoryExtractionJobResponse,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkResponse,
    RegulatoryFrameworkUpdate,
    RequirementAuditHistoryResponse,
    RequirementEditRequest,
    RequirementListResponse,
    RequirementResponse,
    RequirementReviewActionRequest,
)
from app.services.legal_analyst import LegalAnalystService
from app.services.regulatory_service import RegulatoryService

logger = logging.getLogger(__name__)

regulatory_router = APIRouter(prefix="/api/regulatory", tags=["Regulatory Knowledge Base"])
audit_requirements_router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}/requirements",
    tags=["Audit Requirements Mapping"],
)


def _background_extraction_runner(document_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> None:
    """Background task runner for executing Legal Analyst extraction."""
    with SessionLocal() as session:
        try:
            LegalAnalystService.run_extraction_sync(session, document_id, user_id)
        except Exception as e:
            logger.error(f"Background extraction failed for doc {document_id}: {str(e)}", exc_info=True)


# -----------------------------------------------------------------------------
# Regulatory Frameworks
# -----------------------------------------------------------------------------

@regulatory_router.post(
    "/frameworks",
    response_model=RegulatoryFrameworkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_framework(
    payload: RegulatoryFrameworkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryFramework:
    """Create a new regulatory framework."""
    framework = RegulatoryService.create_framework(
        session=db,
        name=payload.name,
        short_name=payload.short_name,
        issuing_authority=payload.issuing_authority,
        description=payload.description,
        jurisdiction=payload.jurisdiction,
        framework_type=payload.framework_type,
        official_source_url=payload.official_source_url,
        version=payload.version,
        effective_date=payload.effective_date,
        framework_metadata=payload.framework_metadata,
    )
    return framework


@regulatory_router.get(
    "/frameworks",
    response_model=List[RegulatoryFrameworkResponse],
)
def list_frameworks(
    search: Optional[str] = Query(None, description="Search term for name/short_name"),
    status: Optional[str] = Query(None, description="Filter by status (active, draft, archived)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[RegulatoryFramework]:
    """List all available regulatory frameworks."""
    return RegulatoryService.list_frameworks(
        session=db,
        organization_id=None,
        include_system=True,
        search=search,
        status=status,
    )


@regulatory_router.get(
    "/frameworks/{framework_id}",
    response_model=RegulatoryFrameworkResponse,
)
def get_framework(
    framework_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryFramework:
    """Retrieve details for a single regulatory framework."""
    framework = RegulatoryService.get_framework(db, framework_id)
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Framework not found")
    return framework


@regulatory_router.patch(
    "/frameworks/{framework_id}",
    response_model=RegulatoryFrameworkResponse,
)
def update_framework(
    framework_id: uuid.UUID,
    payload: RegulatoryFrameworkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryFramework:
    """Update regulatory framework details."""
    framework = RegulatoryService.update_framework(
        session=db,
        framework_id=framework_id,
        **payload.model_dump(exclude_unset=True),
    )
    if not framework:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Framework not found")
    return framework


@regulatory_router.delete(
    "/frameworks/{framework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_framework(
    framework_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a regulatory framework."""
    success = RegulatoryService.delete_framework(db, framework_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Framework not found")


# -----------------------------------------------------------------------------
# Regulatory Documents & Processing
# -----------------------------------------------------------------------------

@regulatory_router.post(
    "/frameworks/{framework_id}/documents",
    response_model=RegulatoryDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_regulatory_document(
    framework_id: uuid.UUID,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    document_number: Optional[str] = Form(None),
    version: str = Form("1.0"),
    source_url: Optional[str] = Form(None),
    issuing_authority: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryDocument:
    """Upload and process an authoritative regulatory document (PDF/DOCX)."""
    file_bytes = await file.read()
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

    try:
        doc = RegulatoryService.upload_and_process_document(
            session=db,
            framework_id=framework_id,
            file_bytes=file_bytes,
            original_filename=file.filename,
            title=title or file.filename,
            document_number=document_number,
            version=version,
            source_url=source_url,
            issuing_authority=issuing_authority,
            uploaded_by=current_user.id,
        )
        return doc
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        logger.error(f"Regulatory doc upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document ingestion failed")


@regulatory_router.get(
    "/frameworks/{framework_id}/documents",
    response_model=List[RegulatoryDocumentResponse],
)
def list_regulatory_documents(
    framework_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[RegulatoryDocument]:
    """List regulatory documents uploaded under a framework."""
    return RegulatoryService.list_documents(db, framework_id)


@regulatory_router.get(
    "/documents/{document_id}",
    response_model=RegulatoryDocumentResponse,
)
def get_regulatory_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryDocument:
    """Get metadata for a specific regulatory document."""
    doc = RegulatoryService.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory document not found")
    return doc


@regulatory_router.get(
    "/documents/{document_id}/chunks",
    response_model=List[RegulatoryDocumentChunkResponse],
)
def get_regulatory_document_chunks(
    document_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[RegulatoryDocumentChunk]:
    """Retrieve text chunks extracted from a regulatory document."""
    doc = RegulatoryService.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory document not found")
    return RegulatoryService.get_document_chunks(db, document_id, limit, offset)


# -----------------------------------------------------------------------------
# Legal Analyst Agent Extraction
# -----------------------------------------------------------------------------

@regulatory_router.post(
    "/documents/{document_id}/extract",
    response_model=RegulatoryExtractionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_legal_analyst_extraction(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    run_synchronous: bool = Query(False, description="Whether to wait for completion in test mode"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegulatoryExtractionJob:
    """Trigger the Legal Analyst AI agent to extract compliance requirements."""
    doc = RegulatoryService.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regulatory document not found")

    if run_synchronous:
        # Run immediately in-process
        job = LegalAnalystService.run_extraction_sync(db, document_id, current_user.id)
        return job

    # Otherwise run as a background task
    job = RegulatoryExtractionJob(
        regulatory_document_id=document_id,
        status="running",
        model_name="gemini-1.5-flash",
        prompt_version="v1.0",
        chunks_total=doc.chunk_count,
        chunks_processed=0,
        requirements_extracted=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_background_extraction_runner, document_id, current_user.id)
    return job


@regulatory_router.get(
    "/documents/{document_id}/jobs",
    response_model=List[RegulatoryExtractionJobResponse],
)
def list_document_extraction_jobs(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[RegulatoryExtractionJob]:
    """List execution jobs for a regulatory document."""
    query = (
        select(RegulatoryExtractionJob)
        .where(RegulatoryExtractionJob.regulatory_document_id == document_id)
        .order_by(RegulatoryExtractionJob.created_at.desc())
    )
    return list(db.execute(query).scalars().all())


# -----------------------------------------------------------------------------
# Requirements Review Workflow
# -----------------------------------------------------------------------------

@regulatory_router.get(
    "/requirements",
    response_model=RequirementListResponse,
)
def list_requirements(
    framework_id: Optional[uuid.UUID] = Query(None),
    document_id: Optional[uuid.UUID] = Query(None),
    review_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RequirementListResponse:
    """List compliance requirements across frameworks with filtering."""
    items, total = RegulatoryService.list_requirements(
        session=db,
        framework_id=framework_id,
        document_id=document_id,
        review_status=review_status,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    return RequirementListResponse(
        items=[RequirementResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@regulatory_router.get(
    "/requirements/{requirement_id}",
    response_model=RequirementResponse,
)
def get_requirement(
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    """Get single requirement with full citations and metadata."""
    req = RegulatoryService.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return req


@regulatory_router.post(
    "/requirements/{requirement_id}/approve",
    response_model=RequirementResponse,
)
def approve_requirement(
    requirement_id: uuid.UUID,
    payload: Optional[RequirementReviewActionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    """Approve an extracted requirement."""
    try:
        return RegulatoryService.approve_requirement(
            session=db,
            requirement_id=requirement_id,
            reviewer_id=current_user.id,
            reason=payload.reason if payload else None,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@regulatory_router.post(
    "/requirements/{requirement_id}/reject",
    response_model=RequirementResponse,
)
def reject_requirement(
    requirement_id: uuid.UUID,
    payload: RequirementReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    """Reject an extracted requirement."""
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection reason required")
    try:
        return RegulatoryService.reject_requirement(
            session=db,
            requirement_id=requirement_id,
            reviewer_id=current_user.id,
            reason=payload.reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@regulatory_router.post(
    "/requirements/{requirement_id}/edit",
    response_model=RequirementResponse,
)
def edit_requirement(
    requirement_id: uuid.UUID,
    payload: RequirementEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    """Edit requirement fields and record the audit history."""
    updates = payload.model_dump(exclude_unset=True)
    reason = updates.pop("reason", None)
    try:
        return RegulatoryService.edit_requirement(
            session=db,
            requirement_id=requirement_id,
            reviewer_id=current_user.id,
            updates=updates,
            reason=reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@regulatory_router.post(
    "/requirements/{requirement_id}/revision",
    response_model=RequirementResponse,
)
def request_requirement_revision(
    requirement_id: uuid.UUID,
    payload: RequirementReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Requirement:
    """Request revision on an extracted requirement."""
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Revision request reason required")
    try:
        return RegulatoryService.request_revision(
            session=db,
            requirement_id=requirement_id,
            reviewer_id=current_user.id,
            reason=payload.reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@regulatory_router.get(
    "/requirements/{requirement_id}/history",
    response_model=List[RequirementAuditHistoryResponse],
)
def get_requirement_history(
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[RequirementAuditHistory]:
    """Retrieve complete audit trail of human edits and review actions for a requirement."""
    query = (
        select(RequirementAuditHistory)
        .where(RequirementAuditHistory.requirement_id == requirement_id)
        .order_by(RequirementAuditHistory.created_at.desc())
    )
    return list(db.execute(query).scalars().all())


# -----------------------------------------------------------------------------
# Audit Requirement Mapping & Evidence Suggestions
# -----------------------------------------------------------------------------

@audit_requirements_router.post(
    "",
    response_model=List[AuditRequirementResponse],
    status_code=status.HTTP_201_CREATED,
)
def map_requirements_to_audit(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    payload: AuditRequirementMapRequest,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
) -> List[AuditRequirement]:
    """Associate approved regulatory requirements with an organization audit."""
    try:
        mappings = RegulatoryService.map_requirements_to_audit(
            session=db,
            audit_id=audit_id,
            organization_id=organization_id,
            requirement_ids=payload.requirement_ids,
            user_id=membership.user_id,
        )
        return mappings
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@audit_requirements_router.get(
    "",
    response_model=List[AuditRequirementResponse],
)
def list_audit_requirements(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    applicability_status: Optional[str] = Query(None),
    membership: OrganizationMember = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> List[AuditRequirement]:
    """List all regulatory requirements mapped to an audit."""
    return RegulatoryService.list_audit_requirements(
        session=db,
        audit_id=audit_id,
        organization_id=organization_id,
        applicability_status=applicability_status,
    )


@audit_requirements_router.patch(
    "/{requirement_id}",
    response_model=AuditRequirementResponse,
)
def update_audit_requirement(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: AuditRequirementUpdateRequest,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
) -> AuditRequirement:
    """Update applicability status and justification of an audit requirement."""
    try:
        return RegulatoryService.update_audit_requirement(
            session=db,
            audit_id=audit_id,
            requirement_id=requirement_id,
            organization_id=organization_id,
            applicability_status=payload.applicability_status,
            applicability_reason=payload.applicability_reason,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@audit_requirements_router.delete(
    "/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_audit_requirement(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    requirement_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
) -> None:
    """Remove a requirement association from an audit."""
    success = RegulatoryService.remove_audit_requirement(
        session=db,
        audit_id=audit_id,
        requirement_id=requirement_id,
        organization_id=organization_id,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit requirement not found")


@audit_requirements_router.get(
    "/{requirement_id}/evidence-suggestions",
    response_model=List[AuditEvidenceSuggestionResponse],
)
def suggest_audit_evidence(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    requirement_id: uuid.UUID,
    membership: OrganizationMember = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Suggest potentially relevant audit evidence documents based on requirement scope."""
    return RegulatoryService.suggest_audit_evidence(
        session=db,
        audit_id=audit_id,
        requirement_id=requirement_id,
        organization_id=organization_id,
    )

