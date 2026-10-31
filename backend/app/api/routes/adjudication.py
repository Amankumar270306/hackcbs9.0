"""API routes for Adjudicator: Cross-Agent Consensus, Reconciliation, Contradictions & Human Review (Milestone 7)."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import SessionLocal, get_db
from app.database.models.identity import OrganizationMember, User
from app.schemas.adjudication import (
    AdjudicationContradictionResponse,
    AdjudicationDecisionDetailResponse,
    AdjudicationDecisionResponse,
    AdjudicationReadinessResponse,
    AdjudicationRunResponse,
    AdjudicationStaleStatusResponse,
    ContradictionResolveRequest,
    DecisionEditRequest,
    DecisionReviewActionRequest,
)
from app.services.adjudication_service import AdjudicationService
from app.services.adjudicator import AdjudicatorPipeline

logger = logging.getLogger(__name__)

adjudication_router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}",
    tags=["Adjudicator & Consensus"],
)


class AdjudicationRunTriggerRequest(BaseModel):
    model_name: Optional[str] = Field(None, description="Gemini model name")
    run_in_background: bool = Field(False, description="Whether to execute asynchronously")


def _run_adjudication_in_background(run_id: UUID) -> None:
    """Background task worker executing adjudication with a dedicated DB session."""
    with SessionLocal() as db:
        try:
            import asyncio
            asyncio.run(AdjudicatorPipeline.run_adjudication(db, run_id))
        except Exception as e:
            logger.exception("Background adjudication failed for run %s: %s", run_id, str(e))


# ============================================================================
# Readiness & Adjudication Runs
# ============================================================================

@adjudication_router.get(
    "/adjudication-readiness",
    response_model=AdjudicationReadinessResponse,
    summary="Pre-flight readiness check for Adjudicator consensus",
)
@adjudication_router.get(
    "/adjudication/readiness",
    response_model=AdjudicationReadinessResponse,
    include_in_schema=False,
)
def check_adjudication_readiness(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Evaluates whether an audit has sufficient input sources across agents for an adjudication run."""
    try:
        return AdjudicationService.check_readiness(db, organization_id, audit_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed checking adjudication readiness: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to check readiness.")


@adjudication_router.post(
    "/adjudication",
    response_model=AdjudicationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an Adjudicator consensus run across all agents",
)
@adjudication_router.post(
    "/adjudication-runs",
    response_model=AdjudicationRunResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def trigger_adjudication_run(
    organization_id: UUID,
    audit_id: UUID,
    req: Optional[AdjudicationRunTriggerRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
):
    """Dispatches cross-agent reconciliation and consensus adjudication."""
    model_name = req.model_name if req and req.model_name else None
    run_in_bg = req.run_in_background if req else False

    try:
        created_run = AdjudicationService.create_adjudication_run(
            db=db,
            organization_id=organization_id,
            audit_id=audit_id,
            model_name=model_name,
        )

        if run_in_bg:
            background_tasks.add_task(_run_adjudication_in_background, created_run.id)
            return created_run
        else:
            # Synchronous execution for immediate turnaround and testing
            completed_run = await AdjudicatorPipeline.run_adjudication(db, created_run.id)
            return AdjudicationRunResponse.model_validate(completed_run)

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to trigger adjudication run: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Adjudication run failed: {str(exc)}")


@adjudication_router.get(
    "/adjudication-runs",
    response_model=List[AdjudicationRunResponse],
    summary="List historical adjudication runs",
)
@adjudication_router.get(
    "/adjudication/runs",
    response_model=List[AdjudicationRunResponse],
    include_in_schema=False,
)
def list_adjudication_runs(
    organization_id: UUID,
    audit_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Lists past execution runs of the Adjudicator."""
    return AdjudicationService.list_adjudication_runs(db, organization_id, audit_id, limit, offset)


@adjudication_router.get(
    "/adjudication-runs/{run_id}",
    response_model=AdjudicationRunResponse,
    summary="Get details of a specific adjudication run",
)
def get_adjudication_run(
    organization_id: UUID,
    audit_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Retrieves full metrics and execution details of an adjudication run."""
    try:
        return AdjudicationService.get_adjudication_run(db, organization_id, audit_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ============================================================================
# Adjudication Decisions
# ============================================================================

@adjudication_router.get(
    "/adjudication-decisions",
    response_model=List[AdjudicationDecisionResponse],
    summary="List adjudication decisions with filters",
)
@adjudication_router.get(
    "/adjudication/decisions",
    response_model=List[AdjudicationDecisionResponse],
    include_in_schema=False,
)
def list_adjudication_decisions(
    organization_id: UUID,
    audit_id: UUID,
    category: Optional[str] = Query(None, description="Filter by decision category"),
    outcome: Optional[str] = Query(None, description="Filter by outcome status"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    is_provisional: Optional[bool] = Query(None, description="Filter provisional decisions"),
    search: Optional[str] = Query(None, description="Search in summary or reasoning"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Lists structured consensus decisions for requirements, threats, and controls."""
    return AdjudicationService.list_decisions(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        category=category,
        outcome=outcome,
        review_status=review_status,
        is_provisional=is_provisional,
        search=search,
        limit=limit,
        offset=offset,
    )


@adjudication_router.get(
    "/adjudication-decisions/{decision_id}",
    response_model=AdjudicationDecisionDetailResponse,
    summary="Get detailed adjudication decision with source references and audit history",
)
def get_adjudication_decision(
    organization_id: UUID,
    audit_id: UUID,
    decision_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Retrieves an adjudication decision with its full reasoning, citations, and review history."""
    try:
        return AdjudicationService.get_decision(db, organization_id, audit_id, decision_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@adjudication_router.post(
    "/adjudication-decisions/{decision_id}/review",
    response_model=AdjudicationDecisionResponse,
    summary="Perform human review action on an adjudication decision",
)
def review_adjudication_decision(
    organization_id: UUID,
    audit_id: UUID,
    decision_id: UUID,
    req: DecisionReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
):
    """Executes a human review action (approve, reject with justification, request more info, reassess)."""
    try:
        return AdjudicationService.review_decision(
            db=db,
            organization_id=organization_id,
            audit_id=audit_id,
            decision_id=decision_id,
            user_id=current_user.id,
            req=req,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@adjudication_router.patch(
    "/adjudication-decisions/{decision_id}",
    response_model=AdjudicationDecisionResponse,
    summary="Edit an adjudication decision with audit trail recording",
)
def edit_adjudication_decision(
    organization_id: UUID,
    audit_id: UUID,
    decision_id: UUID,
    req: DecisionEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
):
    """Updates an adjudication decision's parameters and creates an immutable audit log entry."""
    try:
        return AdjudicationService.edit_decision(
            db=db,
            organization_id=organization_id,
            audit_id=audit_id,
            decision_id=decision_id,
            user_id=current_user.id,
            req=req,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Contradictions
# ============================================================================

@adjudication_router.get(
    "/adjudication-contradictions",
    response_model=List[AdjudicationContradictionResponse],
    summary="List cross-agent contradictions and conflicts",
)
@adjudication_router.get(
    "/adjudication/contradictions",
    response_model=List[AdjudicationContradictionResponse],
    include_in_schema=False,
)
def list_adjudication_contradictions(
    organization_id: UUID,
    audit_id: UUID,
    category: Optional[str] = Query(None, description="Filter by contradiction category"),
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Lists contradictions detected between agents or source documents."""
    return AdjudicationService.list_contradictions(
        db=db,
        organization_id=organization_id,
        audit_id=audit_id,
        category=category,
        resolution_status=resolution_status,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@adjudication_router.get(
    "/adjudication-contradictions/{contradiction_id}",
    response_model=AdjudicationContradictionResponse,
    summary="Get details of a specific contradiction",
)
def get_adjudication_contradiction(
    organization_id: UUID,
    audit_id: UUID,
    contradiction_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Retrieves full details of a contradiction, conflicting claims, and resolution history."""
    try:
        return AdjudicationService.get_contradiction(db, organization_id, audit_id, contradiction_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@adjudication_router.post(
    "/adjudication-contradictions/{contradiction_id}/resolve",
    response_model=AdjudicationContradictionResponse,
    summary="Resolve or update status of a contradiction",
)
def resolve_adjudication_contradiction(
    organization_id: UUID,
    audit_id: UUID,
    contradiction_id: UUID,
    req: ContradictionResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
):
    """Resolves a contradiction or requests clarification with mandatory justification."""
    try:
        return AdjudicationService.resolve_contradiction(
            db=db,
            organization_id=organization_id,
            audit_id=audit_id,
            contradiction_id=contradiction_id,
            user_id=current_user.id,
            req=req,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Stale Status
# ============================================================================

@adjudication_router.get(
    "/adjudication-stale-status",
    response_model=AdjudicationStaleStatusResponse,
    summary="Check if adjudication decisions are stale due to source changes",
)
def check_adjudication_stale_status(
    organization_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    membership: OrganizationMember = Depends(get_current_membership),
):
    """Detects if any upstream requirements, threats, or controls were modified since the last adjudication run."""
    try:
        return AdjudicationService.check_stale_status(db, organization_id, audit_id)
    except Exception as exc:
        logger.exception("Failed to check stale status: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to check stale status.")

