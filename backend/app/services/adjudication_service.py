"""Adjudication management service handling execution, consensus decisions, contradictions, and human reviews."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database.models.adjudication import (
    AdjudicationAuditHistory,
    AdjudicationContradiction,
    AdjudicationDecision,
    AdjudicationRun,
    AdjudicationSource,
)
from app.database.models.assessments import ControlAssessment, Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.defence import DiscoveredControl
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import Finding
from app.database.models.identity import User
from app.database.models.regulatory import AuditRequirement
from app.schemas.adjudication import (
    AdjudicationAuditHistoryResponse,
    AdjudicationContradictionResponse,
    AdjudicationDecisionDetailResponse,
    AdjudicationDecisionResponse,
    AdjudicationReadinessResponse,
    AdjudicationRunResponse,
    AdjudicationSourceResponse,
    AdjudicationStaleStatusResponse,
    ContradictionResolveRequest,
    DecisionEditRequest,
    DecisionReviewActionRequest,
)
from app.services.adjudicator import AdjudicatorPipeline

logger = logging.getLogger(__name__)


class AdjudicationService:
    """Service handling Adjudicator operations, decision catalog, and human review workflows."""

    @staticmethod
    def check_readiness(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
    ) -> AdjudicationReadinessResponse:
        """Evaluates whether an audit has usable source data across agents for an adjudication run."""
        audit = db.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        ).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {audit_id} not found.")

        # Requirements
        req_query = (
            select(Requirement.review_status, AuditRequirement.applicability_status)
            .join(AuditRequirement, AuditRequirement.requirement_id == Requirement.id)
            .where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.organization_id == organization_id,
            )
        )
        req_rows = list(db.execute(req_query).all())
        total_reqs = len(req_rows)
        approved_reqs = sum(1 for r_status, a_status in req_rows if (r_status or "").lower() == "approved")
        pending_reqs = sum(1 for r_status, a_status in req_rows if (r_status or "").lower() in ("pending", "pending_review", "under_review", ""))

        # Threats
        threat_query = select(Threat.review_status).where(
            Threat.audit_id == audit_id,
            Threat.organization_id == organization_id,
        )
        threat_statuses = list(db.execute(threat_query).scalars().all())
        total_threats = len(threat_statuses)
        accepted_threats = sum(1 for s in threat_statuses if (s or "").lower() == "accepted")
        pending_threats = sum(1 for s in threat_statuses if (s or "").lower() in ("pending", "needs_review", ""))

        # Controls & Assessments
        controls_count = db.execute(
            select(func.count(DiscoveredControl.id)).where(
                DiscoveredControl.audit_id == audit_id,
                DiscoveredControl.organization_id == organization_id,
            )
        ).scalar() or 0

        assessments_count = db.execute(
            select(func.count(ControlAssessment.id)).where(
                ControlAssessment.audit_id == audit_id,
                ControlAssessment.organization_id == organization_id,
            )
        ).scalar() or 0

        findings_count = db.execute(
            select(func.count(Finding.id)).where(
                Finding.audit_id == audit_id,
                Finding.organization_id == organization_id,
            )
        ).scalar() or 0

        # Evidence document chunks
        doc_subq = select(AuditDocument.id).where(
            AuditDocument.audit_id == audit_id,
            AuditDocument.organization_id == organization_id,
        )
        chunks_count = db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.audit_document_id.in_(doc_subq))
        ).scalar() or 0

        notes: List[str] = []
        has_legal = total_reqs > 0
        has_threats = total_threats > 0
        has_defence = controls_count > 0 or assessments_count > 0

        if not has_legal and not has_threats and not has_defence and chunks_count == 0:
            is_ready = False
            notes.append("No source data found. Upload audit documents or run Legal Analyst / Adversarial Strategist / Defence Auditor first.")
        else:
            is_ready = True
            if approved_reqs > 0:
                notes.append(f"{approved_reqs} approved regulatory requirement(s) ready for primary reconciliation.")
            elif pending_reqs > 0:
                notes.append(f"{pending_reqs} requirement(s) are pending review; will produce provisional conclusions.")
            else:
                notes.append("No regulatory requirements mapped to this audit.")

            if accepted_threats > 0:
                notes.append(f"{accepted_threats} accepted threat scenario(s) ready for reconciliation.")
            elif pending_threats > 0:
                notes.append(f"{pending_threats} threat scenario(s) pending review; will produce provisional conclusions.")

            if controls_count > 0:
                notes.append(f"{controls_count} discovered security control(s) available for safeguard evaluation.")

        return AdjudicationReadinessResponse(
            audit_id=audit_id,
            is_ready=is_ready,
            requirements_count=total_reqs,
            approved_requirements_count=approved_reqs,
            pending_requirements_count=pending_reqs,
            threats_count=total_threats,
            accepted_threats_count=accepted_threats,
            pending_threats_count=pending_threats,
            controls_count=controls_count,
            assessments_count=assessments_count,
            findings_count=findings_count,
            evidence_chunks_count=chunks_count,
            readiness_notes=notes,
            has_legal_analyst_data=has_legal,
            has_adversarial_strategist_data=has_threats,
            has_defence_auditor_data=has_defence,
        )

    @staticmethod
    def create_adjudication_run(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        model_name: Optional[str] = None,
    ) -> AdjudicationRunResponse:
        """Creates an AdjudicationRun record."""
        audit = db.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        ).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {audit_id} not found.")

        run = AdjudicationRun(
            organization_id=organization_id,
            audit_id=audit_id,
            status="pending",
            model_name=model_name or settings.GEMINI_MODEL,
            prompt_version="v1.0",
            input_source_snapshot={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        return AdjudicationRunResponse.model_validate(run)

    @staticmethod
    def list_adjudication_runs(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdjudicationRunResponse]:
        """Lists historical adjudication runs for an audit."""
        stmt = (
            select(AdjudicationRun)
            .where(
                AdjudicationRun.audit_id == audit_id,
                AdjudicationRun.organization_id == organization_id,
            )
            .order_by(AdjudicationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        runs = list(db.execute(stmt).scalars().all())
        return [AdjudicationRunResponse.model_validate(r) for r in runs]

    @staticmethod
    def get_adjudication_run(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        run_id: UUID,
    ) -> AdjudicationRunResponse:
        """Retrieves details of a specific adjudication run."""
        stmt = select(AdjudicationRun).where(
            AdjudicationRun.id == run_id,
            AdjudicationRun.audit_id == audit_id,
            AdjudicationRun.organization_id == organization_id,
        )
        run = db.execute(stmt).scalar_one_or_none()
        if not run:
            raise ValueError(f"AdjudicationRun {run_id} not found.")
        return AdjudicationRunResponse.model_validate(run)

    @staticmethod
    def list_decisions(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        category: Optional[str] = None,
        outcome: Optional[str] = None,
        review_status: Optional[str] = None,
        is_provisional: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdjudicationDecisionResponse]:
        """Lists adjudication decisions with filtering."""
        stmt = (
            select(AdjudicationDecision)
            .options(joinedload(AdjudicationDecision.sources))
            .where(
                AdjudicationDecision.audit_id == audit_id,
                AdjudicationDecision.organization_id == organization_id,
            )
        )

        if category and category.lower() != "all":
            stmt = stmt.where(AdjudicationDecision.decision_category == category)
        if outcome and outcome.lower() != "all":
            stmt = stmt.where(AdjudicationDecision.outcome_status == outcome)
        if review_status and review_status.lower() != "all":
            stmt = stmt.where(AdjudicationDecision.review_status == review_status)
        if is_provisional is not None:
            stmt = stmt.where(AdjudicationDecision.is_provisional == is_provisional)
        if search:
            q = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    AdjudicationDecision.summary.ilike(q),
                    AdjudicationDecision.reasoning.ilike(q),
                )
            )

        stmt = stmt.order_by(AdjudicationDecision.created_at.desc()).offset(offset).limit(limit)
        decisions = list(db.execute(stmt).unique().scalars().all())
        return [AdjudicationDecisionResponse.model_validate(d) for d in decisions]

    @staticmethod
    def get_decision(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        decision_id: UUID,
    ) -> AdjudicationDecisionDetailResponse:
        """Retrieves an adjudication decision with its sources and audit history."""
        stmt = (
            select(AdjudicationDecision)
            .options(
                joinedload(AdjudicationDecision.sources),
                joinedload(AdjudicationDecision.audit_history).joinedload(AdjudicationAuditHistory.user),
            )
            .where(
                AdjudicationDecision.id == decision_id,
                AdjudicationDecision.audit_id == audit_id,
                AdjudicationDecision.organization_id == organization_id,
            )
        )
        decision = db.execute(stmt).unique().scalar_one_or_none()
        if not decision:
            raise ValueError(f"AdjudicationDecision {decision_id} not found.")

        history_items: List[AdjudicationAuditHistoryResponse] = []
        for h in decision.audit_history:
            u_name = h.user.full_name if h.user else None
            h_dict = {
                "id": h.id,
                "user_id": h.user_id,
                "user_name": u_name,
                "action": h.action,
                "previous_status": h.previous_status,
                "new_status": h.new_status,
                "previous_content": h.previous_content,
                "updated_content": h.updated_content,
                "justification": h.justification,
                "created_at": h.created_at,
            }
            history_items.append(AdjudicationAuditHistoryResponse.model_validate(h_dict))

        sources = [AdjudicationSourceResponse.model_validate(s) for s in decision.sources]

        res_dict = {
            "id": decision.id,
            "organization_id": decision.organization_id,
            "audit_id": decision.audit_id,
            "adjudication_run_id": decision.adjudication_run_id,
            "decision_category": decision.decision_category,
            "related_entity_type": decision.related_entity_type,
            "related_entity_id": decision.related_entity_id,
            "outcome_status": decision.outcome_status,
            "summary": decision.summary,
            "reasoning": decision.reasoning,
            "confidence_score": float(decision.confidence_score),
            "is_provisional": decision.is_provisional,
            "requires_human_review": decision.requires_human_review,
            "is_stale": decision.is_stale,
            "evidence_limitations": decision.evidence_limitations,
            "assumptions": decision.assumptions or [],
            "missing_information": decision.missing_information or [],
            "recommended_action": decision.recommended_action,
            "review_status": decision.review_status,
            "reviewed_by": decision.reviewed_by,
            "reviewed_at": decision.reviewed_at,
            "review_notes": decision.review_notes,
            "decision_metadata": decision.decision_metadata or {},
            "created_at": decision.created_at,
            "updated_at": decision.updated_at,
            "sources": sources,
            "audit_history": history_items,
        }
        return AdjudicationDecisionDetailResponse.model_validate(res_dict)

    @staticmethod
    def review_decision(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        decision_id: UUID,
        user_id: UUID,
        req: DecisionReviewActionRequest,
    ) -> AdjudicationDecisionResponse:
        """Executes a human review decision (approve, reject, more_info_requested, reassess)."""
        decision = db.execute(
            select(AdjudicationDecision).where(
                AdjudicationDecision.id == decision_id,
                AdjudicationDecision.audit_id == audit_id,
                AdjudicationDecision.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not decision:
            raise ValueError(f"AdjudicationDecision {decision_id} not found.")

        old_status = decision.review_status
        action = req.action.lower()
        if action in ("approve", "approved"):
            new_status = "approved"
            history_action = "approved"
            decision.requires_human_review = False
        elif action in ("reject", "rejected"):
            new_status = "rejected"
            history_action = "rejected"
        elif action in ("more_info_requested", "request_more_information", "requested_information"):
            new_status = "more_info_requested"
            history_action = "requested_information"
            decision.requires_human_review = True
        elif action in ("reassess", "reassessed", "re-run"):
            new_status = "pending_review"
            history_action = "reassessed"
            decision.is_stale = False
        else:
            raise ValueError(f"Unsupported review action: {req.action}")

        # Record immutable audit history
        history = AdjudicationAuditHistory(
            organization_id=organization_id,
            audit_id=audit_id,
            decision_id=decision.id,
            user_id=user_id,
            action=history_action,
            previous_status=old_status,
            new_status=new_status,
            justification=req.justification,
        )
        db.add(history)

        decision.review_status = new_status
        decision.reviewed_by = user_id
        decision.reviewed_at = datetime.now(timezone.utc)
        decision.review_notes = req.justification

        db.commit()
        db.refresh(decision)
        return AdjudicationDecisionResponse.model_validate(decision)

    @staticmethod
    def edit_decision(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        decision_id: UUID,
        user_id: UUID,
        req: DecisionEditRequest,
    ) -> AdjudicationDecisionResponse:
        """Edits an adjudication decision with audit trail recording."""
        decision = db.execute(
            select(AdjudicationDecision).where(
                AdjudicationDecision.id == decision_id,
                AdjudicationDecision.audit_id == audit_id,
                AdjudicationDecision.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not decision:
            raise ValueError(f"AdjudicationDecision {decision_id} not found.")

        prev_content = {
            "summary": decision.summary,
            "reasoning": decision.reasoning,
            "outcome_status": decision.outcome_status,
            "confidence_score": float(decision.confidence_score),
            "recommended_action": decision.recommended_action,
        }

        if req.summary is not None:
            decision.summary = req.summary
        if req.reasoning is not None:
            decision.reasoning = req.reasoning
        if req.outcome_status is not None:
            decision.outcome_status = req.outcome_status
        if req.confidence_score is not None:
            decision.confidence_score = req.confidence_score
        if req.recommended_action is not None:
            decision.recommended_action = req.recommended_action

        new_content = {
            "summary": decision.summary,
            "reasoning": decision.reasoning,
            "outcome_status": decision.outcome_status,
            "confidence_score": float(decision.confidence_score),
            "recommended_action": decision.recommended_action,
        }

        decision.review_status = "edited"
        decision.reviewed_by = user_id
        decision.reviewed_at = datetime.now(timezone.utc)
        decision.review_notes = req.justification

        history = AdjudicationAuditHistory(
            organization_id=organization_id,
            audit_id=audit_id,
            decision_id=decision.id,
            user_id=user_id,
            action="edited",
            previous_status="pending_review",
            new_status="edited",
            previous_content=prev_content,
            updated_content=new_content,
            justification=req.justification,
        )
        db.add(history)

        db.commit()
        db.refresh(decision)
        return AdjudicationDecisionResponse.model_validate(decision)

    @staticmethod
    def list_contradictions(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        category: Optional[str] = None,
        resolution_status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdjudicationContradictionResponse]:
        """Lists contradictions detected by the Adjudicator."""
        stmt = (
            select(AdjudicationContradiction)
            .where(
                AdjudicationContradiction.audit_id == audit_id,
                AdjudicationContradiction.organization_id == organization_id,
            )
        )

        if category and category.lower() != "all":
            stmt = stmt.where(AdjudicationContradiction.contradiction_category == category)
        if resolution_status and resolution_status.lower() != "all":
            stmt = stmt.where(AdjudicationContradiction.resolution_status == resolution_status)
        if severity and severity.lower() != "all":
            stmt = stmt.where(AdjudicationContradiction.severity == severity)

        stmt = stmt.order_by(AdjudicationContradiction.created_at.desc()).offset(offset).limit(limit)
        contradictions = list(db.execute(stmt).scalars().all())
        return [AdjudicationContradictionResponse.model_validate(c) for c in contradictions]

    @staticmethod
    def get_contradiction(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        contradiction_id: UUID,
    ) -> AdjudicationContradictionResponse:
        """Retrieves details of a specific contradiction."""
        stmt = (
            select(AdjudicationContradiction)
            .options(
                joinedload(AdjudicationContradiction.audit_history).joinedload(AdjudicationAuditHistory.user),
            )
            .where(
                AdjudicationContradiction.id == contradiction_id,
                AdjudicationContradiction.audit_id == audit_id,
                AdjudicationContradiction.organization_id == organization_id,
            )
        )
        contradiction = db.execute(stmt).unique().scalar_one_or_none()
        if not contradiction:
            raise ValueError(f"AdjudicationContradiction {contradiction_id} not found.")

        history_items: List[AdjudicationAuditHistoryResponse] = []
        for h in contradiction.audit_history:
            u_name = h.user.full_name if h.user else None
            h_dict = {
                "id": h.id,
                "user_id": h.user_id,
                "user_name": u_name,
                "action": h.action,
                "previous_status": h.previous_status,
                "new_status": h.new_status,
                "previous_content": h.previous_content,
                "updated_content": h.updated_content,
                "justification": h.justification,
                "created_at": h.created_at,
            }
            history_items.append(AdjudicationAuditHistoryResponse.model_validate(h_dict))

        res_dict = {
            "id": contradiction.id,
            "organization_id": contradiction.organization_id,
            "audit_id": contradiction.audit_id,
            "adjudication_run_id": contradiction.adjudication_run_id,
            "contradiction_category": contradiction.contradiction_category,
            "title": contradiction.title,
            "description": contradiction.description,
            "conflicting_claims": contradiction.conflicting_claims or [],
            "source_references": contradiction.source_references or [],
            "impact": contradiction.impact,
            "severity": contradiction.severity,
            "resolution_status": contradiction.resolution_status,
            "resolution_notes": contradiction.resolution_notes,
            "resolved_by": contradiction.resolved_by,
            "resolved_at": contradiction.resolved_at,
            "created_at": contradiction.created_at,
            "updated_at": contradiction.updated_at,
            "audit_history": history_items,
        }
        return AdjudicationContradictionResponse.model_validate(res_dict)

    @staticmethod
    def resolve_contradiction(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        contradiction_id: UUID,
        user_id: UUID,
        req: ContradictionResolveRequest,
    ) -> AdjudicationContradictionResponse:
        """Resolves or updates status of a contradiction with audit history."""
        contradiction = db.execute(
            select(AdjudicationContradiction).where(
                AdjudicationContradiction.id == contradiction_id,
                AdjudicationContradiction.audit_id == audit_id,
                AdjudicationContradiction.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not contradiction:
            raise ValueError(f"AdjudicationContradiction {contradiction_id} not found.")

        old_status = contradiction.resolution_status
        new_status = req.resolution_status.lower()

        history = AdjudicationAuditHistory(
            organization_id=organization_id,
            audit_id=audit_id,
            contradiction_id=contradiction.id,
            user_id=user_id,
            action="resolved_contradiction" if new_status == "resolved" else "marked_unresolved",
            previous_status=old_status,
            new_status=new_status,
            justification=req.resolution_notes,
        )
        db.add(history)

        contradiction.resolution_status = new_status
        contradiction.resolution_notes = req.resolution_notes
        contradiction.resolved_by = user_id
        contradiction.resolved_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(contradiction)
        return AdjudicationContradictionResponse.model_validate(contradiction)

    @staticmethod
    def check_stale_status(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
    ) -> AdjudicationStaleStatusResponse:
        """Determines if any decisions are stale due to upstream changes in requirements, threats, or controls."""
        latest_run = db.execute(
            select(AdjudicationRun)
            .where(
                AdjudicationRun.audit_id == audit_id,
                AdjudicationRun.organization_id == organization_id,
                AdjudicationRun.status == "completed",
            )
            .order_by(AdjudicationRun.completed_at.desc())
        ).scalars().first()

        if not latest_run or not latest_run.completed_at:
            return AdjudicationStaleStatusResponse(
                has_stale_decisions=False,
                stale_decisions_count=0,
                latest_adjudication_completed_at=None,
                newer_source_changes_count=0,
                stale_reasons=["No completed adjudication run found."],
            )

        cutoff = latest_run.completed_at
        reasons: List[str] = []
        newer_changes = 0

        # Check newer requirement reviews
        newer_reqs = db.execute(
            select(func.count(AuditRequirement.id)).where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.organization_id == organization_id,
                AuditRequirement.updated_at > cutoff,
            )
        ).scalar() or 0
        if newer_reqs > 0:
            newer_changes += newer_reqs
            reasons.append(f"{newer_reqs} regulatory requirement review(s) updated since latest adjudication.")

        # Check newer threat reviews
        newer_threats = db.execute(
            select(func.count(Threat.id)).where(
                Threat.audit_id == audit_id,
                Threat.organization_id == organization_id,
                Threat.updated_at > cutoff,
            )
        ).scalar() or 0
        if newer_threats > 0:
            newer_changes += newer_threats
            reasons.append(f"{newer_threats} threat scenario(s) modified since latest adjudication.")

        # Check newer control reviews
        newer_controls = db.execute(
            select(func.count(DiscoveredControl.id)).where(
                DiscoveredControl.audit_id == audit_id,
                DiscoveredControl.organization_id == organization_id,
                DiscoveredControl.updated_at > cutoff,
            )
        ).scalar() or 0
        if newer_controls > 0:
            newer_changes += newer_controls
            reasons.append(f"{newer_controls} security control(s) updated since latest adjudication.")

        # Count stale decisions
        stale_count = db.execute(
            select(func.count(AdjudicationDecision.id)).where(
                AdjudicationDecision.audit_id == audit_id,
                AdjudicationDecision.organization_id == organization_id,
                AdjudicationDecision.is_stale == True,
            )
        ).scalar() or 0

        # If newer changes exist, update decisions to is_stale = True
        if newer_changes > 0:
            decisions = list(
                db.execute(
                    select(AdjudicationDecision).where(
                        AdjudicationDecision.audit_id == audit_id,
                        AdjudicationDecision.organization_id == organization_id,
                    )
                ).scalars().all()
            )
            for d in decisions:
                d.is_stale = True
            db.commit()
            stale_count = len(decisions)

        return AdjudicationStaleStatusResponse(
            has_stale_decisions=newer_changes > 0 or stale_count > 0,
            stale_decisions_count=stale_count,
            latest_adjudication_completed_at=cutoff,
            newer_source_changes_count=newer_changes,
            stale_reasons=reasons,
        )

