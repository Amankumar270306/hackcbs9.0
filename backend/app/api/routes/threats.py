"""API routes for Adversarial Threat Modeling, Asset Discovery, and Attack Paths (Milestone 5)."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import SessionLocal, get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.threats import (
    AttackPathNodeResponse,
    AttackSurfaceResponse,
    DiscoveredAssetResponse,
    ThreatAnalysisReadinessResponse,
    ThreatAnalysisRunResponse,
    ThreatAnalysisTriggerRequest,
    ThreatDetailResponse,
    ThreatEditRequest,
    ThreatListResponse,
    ThreatRequirementMappingResponse,
    ThreatResponse,
    ThreatReviewActionRequest,
)
from app.services.adversarial_strategist import AdversarialStrategistService
from app.services.threat_analysis_service import ThreatAnalysisService

logger = logging.getLogger(__name__)

threats_router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}",
    tags=["Adversarial Threat Modeling & Attack Paths"],
)


def _run_in_background_worker(run_id: UUID) -> None:
    """Background task worker executing threat modeling with separate db session."""
    with SessionLocal() as db:
        try:
            import asyncio
            asyncio.run(AdversarialStrategistService.run_threat_analysis(db, run_id))
        except Exception as e:
            logger.exception("Background threat analysis worker failed for run %s: %s", run_id, str(e))


# ============================================================================
# Readiness & Threat Analysis Runs
# ============================================================================

@threats_router.get(
    "/threat-readiness",
    response_model=ThreatAnalysisReadinessResponse,
    summary="Pre-flight readiness check for threat analysis",
)
def check_threat_readiness(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> ThreatAnalysisReadinessResponse:
    """Checks whether the audit has approved requirements and evidence documents."""
    return ThreatAnalysisService.check_readiness(db, organization_id, audit_id)


@threats_router.post(
    "/threat-analysis",
    response_model=ThreatAnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Adversarial Threat Analysis Run",
)
async def trigger_threat_analysis(
    organization_id: UUID,
    audit_id: UUID,
    req: ThreatAnalysisTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
) -> ThreatAnalysisRunResponse:
    """Triggers an Adversarial Strategist threat modeling run."""
    if req.run_in_background:
        run = await ThreatAnalysisService.create_analysis_run(
            db, organization_id, audit_id, req
        )
        background_tasks.add_task(_run_in_background_worker, run.id)
        return ThreatAnalysisRunResponse.model_validate(run)

    run = await ThreatAnalysisService.create_analysis_run(
        db, organization_id, audit_id, req
    )
    return ThreatAnalysisRunResponse.model_validate(run)


@threats_router.get(
    "/threat-analysis",
    response_model=List[ThreatAnalysisRunResponse],
    summary="List Threat Analysis Runs",
)
def list_threat_analysis_runs(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[ThreatAnalysisRunResponse]:
    """Lists historical threat modeling runs for this audit."""
    runs = ThreatAnalysisService.list_analysis_runs(db, organization_id, audit_id)
    return [ThreatAnalysisRunResponse.model_validate(r) for r in runs]


@threats_router.get(
    "/threat-analysis/{run_id}",
    response_model=ThreatAnalysisRunResponse,
    summary="Get Threat Analysis Run details",
)
def get_threat_analysis_run(
    organization_id: UUID,
    audit_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> ThreatAnalysisRunResponse:
    """Retrieves status and metrics of a threat analysis execution."""
    run = ThreatAnalysisService.get_analysis_run(db, organization_id, audit_id, run_id)
    return ThreatAnalysisRunResponse.model_validate(run)


@threats_router.post(
    "/threat-analysis/{run_id}/retry",
    response_model=ThreatAnalysisRunResponse,
    summary="Retry a failed Threat Analysis Run",
)
async def retry_threat_analysis_run(
    organization_id: UUID,
    audit_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
) -> ThreatAnalysisRunResponse:
    """Retries a failed threat analysis run."""
    run = await ThreatAnalysisService.retry_analysis_run(db, organization_id, audit_id, run_id)
    return ThreatAnalysisRunResponse.model_validate(run)


# ============================================================================
# Asset Discovery & Attack Surfaces
# ============================================================================

@threats_router.get(
    "/assets",
    response_model=List[DiscoveredAssetResponse],
    summary="List Discovered Assets",
)
def list_discovered_assets(
    organization_id: UUID,
    audit_id: UUID,
    category: Optional[str] = Query(None, description="Filter by asset category"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[DiscoveredAssetResponse]:
    """Lists assets discovered from audit evidence documents."""
    assets = ThreatAnalysisService.list_assets(db, organization_id, audit_id, category=category)
    return [DiscoveredAssetResponse.model_validate(a) for a in assets]


@threats_router.get(
    "/assets/{asset_id}",
    response_model=DiscoveredAssetResponse,
    summary="Get Discovered Asset",
)
def get_discovered_asset(
    organization_id: UUID,
    audit_id: UUID,
    asset_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> DiscoveredAssetResponse:
    """Retrieves details of a discovered asset."""
    asset = ThreatAnalysisService.get_asset(db, organization_id, audit_id, asset_id)
    return DiscoveredAssetResponse.model_validate(asset)


@threats_router.get(
    "/attack-surfaces",
    response_model=List[AttackSurfaceResponse],
    summary="List Attack Surfaces",
)
def list_attack_surfaces(
    organization_id: UUID,
    audit_id: UUID,
    surface_type: Optional[str] = Query(None, description="Filter by surface type"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[AttackSurfaceResponse]:
    """Lists attack surfaces and entry points identified for the system."""
    surfaces = ThreatAnalysisService.list_attack_surfaces(db, organization_id, audit_id, surface_type=surface_type)
    return [AttackSurfaceResponse.model_validate(s) for s in surfaces]


# ============================================================================
# Threat Inventory & Detail
# ============================================================================

@threats_router.get(
    "/threats",
    response_model=ThreatListResponse,
    summary="List Threats with STRIDE & Severity filters",
)
def list_threats(
    organization_id: UUID,
    audit_id: UUID,
    stride_category: Optional[str] = Query(None, description="Filter by STRIDE category"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, very_high, critical)"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    search: Optional[str] = Query(None, description="Search keyword in title or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> ThreatListResponse:
    """Lists threats matching filters with pagination."""
    items, total = ThreatAnalysisService.list_threats(
        db,
        organization_id,
        audit_id,
        stride_category=stride_category,
        severity=severity,
        review_status_filter=review_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return ThreatListResponse(
        threats=items,
        total_count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@threats_router.get(
    "/threats/{threat_id}",
    response_model=ThreatDetailResponse,
    summary="Get Detailed Threat with Attack Path and Citations",
)
def get_threat_detail(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> ThreatDetailResponse:
    """Retrieves single threat with its complete attack tree, evidence references, and requirement mappings."""
    return ThreatAnalysisService.get_threat_detail(db, organization_id, audit_id, threat_id)


# ============================================================================
# Human Review & Editing Controls
# ============================================================================

@threats_router.post(
    "/threats/{threat_id}/accept",
    response_model=ThreatDetailResponse,
    summary="Accept Threat Scenario",
)
def accept_threat(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    action_req: ThreatReviewActionRequest = ThreatReviewActionRequest(action="accept"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
) -> ThreatDetailResponse:
    """Auditor accepts the threat scenario."""
    ThreatAnalysisService.accept_threat(
        db, organization_id, audit_id, threat_id, current_user.id, reason=action_req.reason
    )
    return ThreatAnalysisService.get_threat_detail(db, organization_id, audit_id, threat_id)


@threats_router.post(
    "/threats/{threat_id}/reject",
    response_model=ThreatDetailResponse,
    summary="Reject Threat Scenario",
)
def reject_threat(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    action_req: ThreatReviewActionRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
) -> ThreatDetailResponse:
    """Auditor rejects the threat scenario with required justification."""
    if not action_req.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A justification reason is required when rejecting a threat.",
        )
    ThreatAnalysisService.reject_threat(
        db, organization_id, audit_id, threat_id, current_user.id, reason=action_req.reason
    )
    return ThreatAnalysisService.get_threat_detail(db, organization_id, audit_id, threat_id)


@threats_router.post(
    "/threats/{threat_id}/request-review",
    response_model=ThreatDetailResponse,
    summary="Request More Information for Threat Scenario",
)
def request_more_information(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    action_req: ThreatReviewActionRequest = ThreatReviewActionRequest(action="request_review"),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
) -> ThreatDetailResponse:
    """Flags threat as needing more architectural evidence or clarification."""
    ThreatAnalysisService.request_review_for_threat(
        db, organization_id, audit_id, threat_id, current_user.id, reason=action_req.reason
    )
    return ThreatAnalysisService.get_threat_detail(db, organization_id, audit_id, threat_id)


@threats_router.patch(
    "/threats/{threat_id}",
    response_model=ThreatDetailResponse,
    summary="Edit Threat Scenario with Audit Trail",
)
def edit_threat(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    edit_req: ThreatEditRequest,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    current_user: User = Depends(get_current_user),
) -> ThreatDetailResponse:
    """Modifies threat scenario parameters with recorded change history."""
    ThreatAnalysisService.edit_threat(
        db, organization_id, audit_id, threat_id, current_user.id, edit_req
    )
    return ThreatAnalysisService.get_threat_detail(db, organization_id, audit_id, threat_id)


# ============================================================================
# Attack Path Tree & Requirement Mappings
# ============================================================================

@threats_router.get(
    "/threats/{threat_id}/attack-path",
    response_model=List[AttackPathNodeResponse],
    summary="Get Attack Path Tree Nodes",
)
def get_attack_path(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[AttackPathNodeResponse]:
    """Retrieves structured attack tree nodes for visual rendering."""
    nodes = ThreatAnalysisService.get_attack_path(db, organization_id, audit_id, threat_id)
    return [AttackPathNodeResponse.model_validate(n) for n in nodes]


@threats_router.get(
    "/threats/{threat_id}/requirements",
    response_model=List[ThreatRequirementMappingResponse],
    summary="Get Mapped Regulatory Requirements",
)
def get_threat_requirements(
    organization_id: UUID,
    audit_id: UUID,
    threat_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
    current_user: User = Depends(get_current_user),
) -> List[ThreatRequirementMappingResponse]:
    """Retrieves mapped approved regulatory requirements for this threat."""
    return ThreatAnalysisService.get_threat_requirements(db, organization_id, audit_id, threat_id)

