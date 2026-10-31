"""API routes for Defence Auditor: Control Discovery, Evidence Quality & Gap Assessments (Milestone 6)."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import SessionLocal, get_db
from app.database.models.assessments import ControlAssessment
from app.database.models.identity import OrganizationMember, User
from app.schemas.defence import (
    ControlAssessmentResponse,
    ControlDetailResponse,
    ControlEditRequest,
    ControlReviewActionRequest,
    DefenceAnalysisRunResponse,
    DefenceReadinessResponse,
    DiscoveredControlResponse,
    FindingDetailResponse,
    FindingEditRequest,
    FindingResponse,
    FindingReviewActionRequest,
)
from app.services.defence_auditor import DefenceAuditorService
from app.services.defence_service import DefenceService

logger = logging.getLogger(__name__)

defence_router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}",
    tags=["Defence Auditor & Controls"],
)


class DefenceRunTriggerRequest(BaseModel):
    model_name: Optional[str] = Field("gemini-1.5-flash", description="Gemini model name")
    run_in_background: bool = Field(False, description="Whether to execute asynchronously")


def _run_defence_in_background(run_id: UUID) -> None:
    """Background task worker executing defence analysis with separate db session."""
    with SessionLocal() as db:
        try:
            import asyncio
            asyncio.run(DefenceAuditorService.run_defence_analysis(db, run_id))
        except Exception as e:
            logger.exception("Background defence analysis failed for run %s: %s", run_id, str(e))


# ============================================================================
# Readiness & Defence Analysis Runs
# ============================================================================

@defence_router.get(
    "/defence-readiness",
    response_model=DefenceReadinessResponse,
    summary="Pre-flight readiness check for Defence Auditor",
)
@defence_router.get(
    "/defence/readiness",
    response_model=DefenceReadinessResponse,
    include_in_schema=False,
)
def check_defence_readiness(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> DefenceReadinessResponse:
    """Evaluates whether the audit has approved requirements and evidence documents ready for defence auditing."""
    try:
        return DefenceService.check_readiness(db, organization_id, audit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@defence_router.post(
    "/defence-analysis",
    response_model=DefenceAnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Defence Auditor Analysis Run",
)
@defence_router.post(
    "/defence/runs",
    response_model=DefenceAnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def trigger_defence_analysis(
    organization_id: UUID,
    audit_id: UUID,
    req: DefenceRunTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> DefenceAnalysisRunResponse:
    """Triggers a Defence Auditor evaluation run against audit evidence documents."""
    try:
        run = DefenceService.create_analysis_run(
            db, organization_id, audit_id, model_name=req.model_name
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if req.run_in_background:
        background_tasks.add_task(_run_defence_in_background, run.id)
        return DefenceAnalysisRunResponse.model_validate(run)

    # Synchronous execution
    try:
        completed_run = await DefenceAuditorService.run_defence_analysis(db, run.id)
        return DefenceAnalysisRunResponse.model_validate(completed_run)
    except Exception as e:
        logger.exception("Synchronous defence analysis failed for run %s: %s", run.id, str(e))
        db.refresh(run)
        return DefenceAnalysisRunResponse.model_validate(run)


@defence_router.get(
    "/defence-analysis",
    response_model=List[DefenceAnalysisRunResponse],
    summary="List Defence Analysis Runs",
)
@defence_router.get(
    "/defence/runs",
    response_model=List[DefenceAnalysisRunResponse],
    include_in_schema=False,
)
def list_defence_runs(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[DefenceAnalysisRunResponse]:
    """Lists historical defence analysis runs for this audit."""
    runs = DefenceService.list_analysis_runs(db, organization_id, audit_id)
    return [DefenceAnalysisRunResponse.model_validate(r) for r in runs]


@defence_router.get(
    "/defence-analysis/{run_id}",
    response_model=DefenceAnalysisRunResponse,
    summary="Get Defence Analysis Run details",
)
@defence_router.get(
    "/defence/runs/{run_id}",
    response_model=DefenceAnalysisRunResponse,
    include_in_schema=False,
)
def get_defence_run(
    organization_id: UUID,
    audit_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> DefenceAnalysisRunResponse:
    """Fetches details and metrics of a single defence analysis run."""
    run = DefenceService.get_analysis_run(db, organization_id, audit_id, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found.")
    return DefenceAnalysisRunResponse.model_validate(run)


# ============================================================================
# Discovered Controls & Detail
# ============================================================================

@defence_router.get(
    "/controls",
    response_model=List[DiscoveredControlResponse],
    summary="List Discovered Security Controls",
)
@defence_router.get(
    "/defence/controls",
    response_model=List[DiscoveredControlResponse],
    include_in_schema=False,
)
def list_controls(
    organization_id: UUID,
    audit_id: UUID,
    category: Optional[str] = Query(None, description="Filter by control category"),
    maturity: Optional[str] = Query(None, description="Filter by maturity: policy, design, implementation, operational"),
    implementation_status: Optional[str] = Query(None, description="Filter by implementation status"),
    operational_status: Optional[str] = Query(None, description="Filter by operational status"),
    search: Optional[str] = Query(None, description="Search term for name or description"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[DiscoveredControlResponse]:
    """Lists all discovered controls for an audit."""
    return DefenceService.list_controls(
        db,
        organization_id,
        audit_id,
        category=category,
        maturity=maturity,
        implementation_status=implementation_status,
        operational_status=operational_status,
        search=search,
    )


@defence_router.get(
    "/controls/{control_id}",
    response_model=ControlDetailResponse,
    summary="Get Discovered Control Details",
)
@defence_router.get(
    "/defence/controls/{control_id}",
    response_model=ControlDetailResponse,
    include_in_schema=False,
)
def get_control_detail(
    organization_id: UUID,
    audit_id: UUID,
    control_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> ControlDetailResponse:
    """Returns full details of a control including assessments, requirements, threats, citations, and history."""
    detail = DefenceService.get_control_detail(db, organization_id, audit_id, control_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Control {control_id} not found.")
    return detail


@defence_router.post(
    "/controls/{control_id}/review",
    response_model=DiscoveredControlResponse,
    summary="Perform Human Review Action on Control",
)
@defence_router.post(
    "/defence/controls/{control_id}/review",
    response_model=DiscoveredControlResponse,
    include_in_schema=False,
)
def review_control(
    organization_id: UUID,
    audit_id: UUID,
    control_id: UUID,
    payload: ControlReviewActionRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> DiscoveredControlResponse:
    """Approve, reject (with mandatory reason), request more info, or reassess a control."""
    try:
        ctrl = DefenceService.review_control(
            db, organization_id, audit_id, control_id, current_user, payload
        )
        detail = DefenceService.get_control_detail(db, organization_id, audit_id, ctrl.id)
        return detail  # type: ignore[return-value]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@defence_router.patch(
    "/controls/{control_id}",
    response_model=DiscoveredControlResponse,
    summary="Edit Control Details or Assessment",
)
@defence_router.patch(
    "/defence/controls/{control_id}",
    response_model=DiscoveredControlResponse,
    include_in_schema=False,
)
def edit_control(
    organization_id: UUID,
    audit_id: UUID,
    control_id: UUID,
    payload: ControlEditRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> DiscoveredControlResponse:
    """Edits control specifications or assessment status, logging change history."""
    try:
        ctrl = DefenceService.edit_control(
            db, organization_id, audit_id, control_id, current_user, payload
        )
        detail = DefenceService.get_control_detail(db, organization_id, audit_id, ctrl.id)
        return detail  # type: ignore[return-value]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Findings & Security Gaps
# ============================================================================

@defence_router.get(
    "/findings",
    response_model=List[FindingResponse],
    summary="List Findings and Security Gaps",
)
@defence_router.get(
    "/defence/findings",
    response_model=List[FindingResponse],
    include_in_schema=False,
)
def list_findings(
    organization_id: UUID,
    audit_id: UUID,
    category: Optional[str] = Query(None, description="Filter by finding category"),
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, very_high, critical"),
    evidence_state: Optional[str] = Query(None, description="Filter by evidence state"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    search: Optional[str] = Query(None, description="Search term for title or description"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[FindingResponse]:
    """Lists findings and gaps identified during defence auditing."""
    return DefenceService.list_findings(
        db,
        organization_id,
        audit_id,
        category=category,
        severity=severity,
        evidence_state=evidence_state,
        review_status=review_status,
        search=search,
    )


@defence_router.get(
    "/findings/{finding_id}",
    response_model=FindingDetailResponse,
    summary="Get Finding Detail",
)
@defence_router.get(
    "/defence/findings/{finding_id}",
    response_model=FindingDetailResponse,
    include_in_schema=False,
)
def get_finding_detail(
    organization_id: UUID,
    audit_id: UUID,
    finding_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> FindingDetailResponse:
    """Fetches complete detail of a finding, including related controls and review history."""
    detail = DefenceService.get_finding_detail(db, organization_id, audit_id, finding_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding {finding_id} not found.")
    return detail


@defence_router.post(
    "/findings/{finding_id}/review",
    response_model=FindingResponse,
    summary="Perform Human Review Action on Finding",
)
@defence_router.post(
    "/defence/findings/{finding_id}/review",
    response_model=FindingResponse,
    include_in_schema=False,
)
def review_finding(
    organization_id: UUID,
    audit_id: UUID,
    finding_id: UUID,
    payload: FindingReviewActionRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> FindingResponse:
    """Approve, reject (with mandatory reason), request more info, or reassess a finding."""
    try:
        finding = DefenceService.review_finding(
            db, organization_id, audit_id, finding_id, current_user, payload
        )
        detail = DefenceService.get_finding_detail(db, organization_id, audit_id, finding.id)
        return detail  # type: ignore[return-value]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@defence_router.patch(
    "/findings/{finding_id}",
    response_model=FindingResponse,
    summary="Edit Finding Details",
)
@defence_router.patch(
    "/defence/findings/{finding_id}",
    response_model=FindingResponse,
    include_in_schema=False,
)
def edit_finding(
    organization_id: UUID,
    audit_id: UUID,
    finding_id: UUID,
    payload: FindingEditRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> FindingResponse:
    """Edits finding specifications, deterministically updating risk score if likelihood/impact changes."""
    try:
        finding = DefenceService.edit_finding(
            db, organization_id, audit_id, finding_id, current_user, payload
        )
        detail = DefenceService.get_finding_detail(db, organization_id, audit_id, finding.id)
        return detail  # type: ignore[return-value]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Assessments List
# ============================================================================

@defence_router.get(
    "/assessments",
    response_model=List[ControlAssessmentResponse],
    summary="List Control Assessments",
)
@defence_router.get(
    "/defence/assessments",
    response_model=List[ControlAssessmentResponse],
    include_in_schema=False,
)
def list_assessments(
    organization_id: UUID,
    audit_id: UUID,
    control_id: Optional[UUID] = Query(None, description="Filter by control ID"),
    status: Optional[str] = Query(None, description="Filter by assessment status"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[ControlAssessmentResponse]:
    """Lists control assessments with optional filtering."""
    query = select(ControlAssessment).where(
        ControlAssessment.organization_id == organization_id,
        ControlAssessment.audit_id == audit_id,
    )
    if control_id:
        query = query.where(ControlAssessment.control_id == control_id)
    if status:
        query = query.where(ControlAssessment.status == status)
    if review_status:
        query = query.where(ControlAssessment.review_status == review_status)

    query = query.order_by(ControlAssessment.created_at.desc())
    assessments = list(db.execute(query).scalars().all())
    return [ControlAssessmentResponse.model_validate(a) for a in assessments]

