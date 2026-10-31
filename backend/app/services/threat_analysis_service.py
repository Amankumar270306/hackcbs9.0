"""Business logic and query service for Adversarial Threat Modeling (Milestone 5)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.models.assessments import Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.regulatory import AuditRequirement, RegulatoryFramework
from app.database.models.threats import (
    AttackPathNode,
    AttackSurface,
    DiscoveredAsset,
    ThreatAnalysisRun,
    ThreatAuditHistory,
    ThreatEvidenceReference,
    ThreatRequirementMapping,
)
from app.database.models.identity import User
from app.schemas.threats import (
    AttackPathNodeResponse,
    AttackSurfaceResponse,
    DiscoveredAssetResponse,
    ThreatAnalysisReadinessResponse,
    ThreatAnalysisTriggerRequest,
    ThreatAuditHistoryResponse,
    ThreatDetailResponse,
    ThreatEditRequest,
    ThreatEvidenceResponse,
    ThreatRequirementMappingResponse,
    ThreatResponse,
)
from app.services.adversarial_strategist import (
    AdversarialStrategistService,
    compute_risk_and_severity,
)

logger = logging.getLogger(__name__)


class ThreatAnalysisService:
    """Service providing query and human-in-the-loop review capabilities for threats."""

    @staticmethod
    def _verify_audit(db: Session, organization_id: UUID, audit_id: UUID) -> Audit:
        """Verifies that the audit exists and belongs to the given organization."""
        audit = db.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        ).scalar_one_or_none()
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit {audit_id} not found in this organization.",
            )
        return audit

    @classmethod
    def check_readiness(
        cls, db: Session, organization_id: UUID, audit_id: UUID
    ) -> ThreatAnalysisReadinessResponse:
        """Performs a pre-flight readiness check for threat analysis on an audit."""
        audit = cls._verify_audit(db, organization_id, audit_id)

        # Count approved vs pending requirements for this audit
        approved_req_count = db.execute(
            select(func.count(AuditRequirement.id))
            .join(Requirement, Requirement.id == AuditRequirement.requirement_id)
            .where(
                AuditRequirement.audit_id == audit.id,
                AuditRequirement.applicability_status == "applicable",
                Requirement.review_status == "approved",
            )
        ).scalar_one() or 0

        pending_req_count = db.execute(
            select(func.count(AuditRequirement.id))
            .join(Requirement, Requirement.id == AuditRequirement.requirement_id)
            .where(
                AuditRequirement.audit_id == audit.id,
                AuditRequirement.applicability_status == "applicable",
                Requirement.review_status != "approved",
            )
        ).scalar_one() or 0

        # Count audit documents and chunks
        docs_count = db.execute(
            select(func.count(AuditDocument.id)).where(
                AuditDocument.audit_id == audit.id,
                AuditDocument.organization_id == organization_id,
            )
        ).scalar_one() or 0

        chunks_count = db.execute(
            select(func.count(DocumentChunk.id))
            .join(AuditDocument, AuditDocument.id == DocumentChunk.audit_document_id)
            .where(
                AuditDocument.audit_id == audit.id,
                AuditDocument.organization_id == organization_id,
            )
        ).scalar_one() or 0

        # Count previous threat runs
        runs_count = db.execute(
            select(func.count(ThreatAnalysisRun.id)).where(
                ThreatAnalysisRun.audit_id == audit.id,
                ThreatAnalysisRun.organization_id == organization_id,
            )
        ).scalar_one() or 0

        validation_messages: List[str] = []
        is_ready = True

        if docs_count == 0:
            validation_messages.append("No audit documents have been uploaded yet. Upload architecture or policy documents.")
            is_ready = False
        elif chunks_count == 0:
            validation_messages.append("Audit documents have not been processed into chunks yet.")
            is_ready = False

        if approved_req_count == 0:
            validation_messages.append("No approved regulatory requirements are mapped to this audit. Approve extracted requirements in the Regulatory Knowledge Base.")
            is_ready = False

        if pending_req_count > 0:
            validation_messages.append(f"Notice: {pending_req_count} requirements are still pending review. They will be excluded from threat mapping.")

        if is_ready and not validation_messages:
            validation_messages.append("System is fully ready for Adversarial Threat Modeling and Attack Path generation.")

        return ThreatAnalysisReadinessResponse(
            audit_id=audit.id,
            audit_title=audit.title,
            is_ready=is_ready,
            approved_requirements_count=approved_req_count,
            pending_requirements_count=pending_req_count,
            documents_count=docs_count,
            chunks_count=chunks_count,
            previous_runs_count=runs_count,
            validation_messages=validation_messages,
        )

    @classmethod
    async def create_analysis_run(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        req: ThreatAnalysisTriggerRequest,
    ) -> ThreatAnalysisRun:
        """Creates and optionally executes a threat analysis run."""
        audit = cls._verify_audit(db, organization_id, audit_id)

        doc_ids = [str(d) for d in req.document_ids] if req.document_ids else []
        req_ids = [str(r) for r in req.requirement_ids] if req.requirement_ids else []

        run = ThreatAnalysisRun(
            organization_id=organization_id,
            audit_id=audit.id,
            status="pending",
            model_name=req.model_name or "gemini-1.5-flash",
            prompt_version="v1.0",
            input_document_ids=doc_ids,
            input_requirement_ids=req_ids,
            execution_metrics={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Run synchronously if not background requested
        if not req.run_in_background:
            run = await AdversarialStrategistService.run_threat_analysis(db, run.id)

        return run

    @classmethod
    def list_analysis_runs(
        cls, db: Session, organization_id: UUID, audit_id: UUID
    ) -> List[ThreatAnalysisRun]:
        """Lists all threat analysis runs for an audit."""
        cls._verify_audit(db, organization_id, audit_id)
        runs = db.execute(
            select(ThreatAnalysisRun)
            .where(
                ThreatAnalysisRun.organization_id == organization_id,
                ThreatAnalysisRun.audit_id == audit_id,
            )
            .order_by(ThreatAnalysisRun.created_at.desc())
        ).scalars().all()
        return list(runs)

    @classmethod
    def get_analysis_run(
        cls, db: Session, organization_id: UUID, audit_id: UUID, run_id: UUID
    ) -> ThreatAnalysisRun:
        """Retrieves a single threat analysis run."""
        cls._verify_audit(db, organization_id, audit_id)
        run = db.execute(
            select(ThreatAnalysisRun).where(
                ThreatAnalysisRun.id == run_id,
                ThreatAnalysisRun.organization_id == organization_id,
                ThreatAnalysisRun.audit_id == audit_id,
            )
        ).scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Threat analysis run {run_id} not found.",
            )
        return run

    @classmethod
    async def retry_analysis_run(
        cls, db: Session, organization_id: UUID, audit_id: UUID, run_id: UUID
    ) -> ThreatAnalysisRun:
        """Retries a failed threat analysis run."""
        run = cls.get_analysis_run(db, organization_id, audit_id, run_id)
        if run.status not in ("failed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot retry run with status '{run.status}'. Only failed or cancelled runs can be retried.",
            )
        return await AdversarialStrategistService.run_threat_analysis(db, run.id)

    @classmethod
    def list_assets(
        cls, db: Session, organization_id: UUID, audit_id: UUID, category: Optional[str] = None
    ) -> List[DiscoveredAsset]:
        """Lists discovered assets for an audit."""
        cls._verify_audit(db, organization_id, audit_id)
        query = select(DiscoveredAsset).where(
            DiscoveredAsset.organization_id == organization_id,
            DiscoveredAsset.audit_id == audit_id,
        )
        if category:
            query = query.where(DiscoveredAsset.asset_category == category)
        query = query.order_by(DiscoveredAsset.criticality.desc(), DiscoveredAsset.name.asc())
        return list(db.execute(query).scalars().all())

    @classmethod
    def get_asset(
        cls, db: Session, organization_id: UUID, audit_id: UUID, asset_id: UUID
    ) -> DiscoveredAsset:
        """Retrieves a discovered asset."""
        cls._verify_audit(db, organization_id, audit_id)
        asset = db.execute(
            select(DiscoveredAsset).where(
                DiscoveredAsset.id == asset_id,
                DiscoveredAsset.organization_id == organization_id,
                DiscoveredAsset.audit_id == audit_id,
            )
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
        return asset

    @classmethod
    def list_attack_surfaces(
        cls, db: Session, organization_id: UUID, audit_id: UUID, surface_type: Optional[str] = None
    ) -> List[AttackSurface]:
        """Lists attack surfaces for an audit."""
        cls._verify_audit(db, organization_id, audit_id)
        query = select(AttackSurface).where(
            AttackSurface.organization_id == organization_id,
            AttackSurface.audit_id == audit_id,
        )
        if surface_type:
            query = query.where(AttackSurface.surface_type == surface_type)
        query = query.order_by(AttackSurface.created_at.desc())
        return list(db.execute(query).scalars().all())

    @classmethod
    def list_threats(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        stride_category: Optional[str] = None,
        severity: Optional[str] = None,
        review_status_filter: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ThreatResponse], int]:
        """Lists threats with STRIDE, severity, review status, and search filters."""
        cls._verify_audit(db, organization_id, audit_id)

        query = select(Threat).where(Threat.audit_id == audit_id)

        if stride_category:
            query = query.where(
                or_(
                    Threat.stride_category.ilike(stride_category),
                    Threat.threat_category.ilike(stride_category),
                )
            )

        if severity:
            query = query.where(Threat.severity == severity.lower())

        if review_status_filter:
            query = query.where(Threat.review_status == review_status_filter.lower())

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Threat.threat_title.ilike(term),
                    Threat.threat_description.ilike(term),
                    Threat.attack_objective.ilike(term),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = db.execute(count_stmt).scalar_one() or 0

        # Order by risk score desc
        query = query.order_by(Threat.risk_score.desc(), Threat.created_at.desc())
        offset = (page - 1) * page_size
        threats = db.execute(query.offset(offset).limit(page_size)).scalars().all()

        # Enrich with sub-counts
        threat_responses: List[ThreatResponse] = []
        for t in threats:
            req_count = db.execute(
                select(func.count(ThreatRequirementMapping.id)).where(ThreatRequirementMapping.threat_id == t.id)
            ).scalar_one() or 0

            node_count = db.execute(
                select(func.count(AttackPathNode.id)).where(AttackPathNode.threat_id == t.id)
            ).scalar_one() or 0

            threat_responses.append(
                ThreatResponse(
                    id=t.id,
                    audit_id=t.audit_id,
                    threat_analysis_run_id=t.threat_analysis_run_id,
                    threat_title=t.threat_title,
                    threat_description=t.threat_description,
                    stride_category=t.stride_category,
                    threat_category=t.threat_category,
                    attack_objective=t.attack_objective,
                    attack_vector=t.attack_vector,
                    entry_point=t.entry_point,
                    cia_confidentiality=t.cia_confidentiality,
                    cia_integrity=t.cia_integrity,
                    cia_availability=t.cia_availability,
                    likelihood_score=t.likelihood_score,
                    impact_score=t.impact_score,
                    risk_score=t.risk_score,
                    severity=t.severity,
                    is_provisional=t.is_provisional,
                    confidence_score=float(t.confidence_score),
                    review_status=t.review_status,
                    review_reason=t.review_reason,
                    reviewed_at=t.reviewed_at,
                    mapped_requirements_count=req_count,
                    attack_nodes_count=node_count,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
            )

        return threat_responses, total_count

    @classmethod
    def get_threat_detail(
        cls, db: Session, organization_id: UUID, audit_id: UUID, threat_id: UUID
    ) -> ThreatDetailResponse:
        """Retrieves full threat details with attack path, evidence, mappings, and history."""
        cls._verify_audit(db, organization_id, audit_id)

        threat = db.execute(
            select(Threat).where(Threat.id == threat_id, Threat.audit_id == audit_id)
        ).scalar_one_or_none()
        if not threat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat not found.")

        # Attack path nodes
        nodes = db.execute(
            select(AttackPathNode)
            .where(AttackPathNode.threat_id == threat.id)
            .order_by(AttackPathNode.sequence_number.asc())
        ).scalars().all()
        node_responses = [AttackPathNodeResponse.model_validate(n) for n in nodes]

        # Evidence references
        evs = db.execute(
            select(ThreatEvidenceReference)
            .where(ThreatEvidenceReference.threat_id == threat.id)
            .order_by(ThreatEvidenceReference.created_at.asc())
        ).scalars().all()
        ev_responses = [ThreatEvidenceResponse.model_validate(e) for e in evs]

        # Requirement mappings (joined with Requirement and RegulatoryFramework)
        maps = db.execute(
            select(
                ThreatRequirementMapping,
                Requirement.requirement_code,
                Requirement.title.label("requirement_title"),
                Requirement.category,
                func.coalesce(RegulatoryFramework.name, Requirement.framework).label("framework_name"),
            )
            .join(Requirement, Requirement.id == ThreatRequirementMapping.requirement_id)
            .outerjoin(RegulatoryFramework, RegulatoryFramework.id == Requirement.framework_id)
            .where(ThreatRequirementMapping.threat_id == threat.id)
            .order_by(ThreatRequirementMapping.created_at.asc())
        ).all()

        map_responses: List[ThreatRequirementMappingResponse] = []
        for row in maps:
            m = row[0]
            map_responses.append(
                ThreatRequirementMappingResponse(
                    id=m.id,
                    threat_id=m.threat_id,
                    requirement_id=m.requirement_id,
                    relationship_type=m.relationship_type,
                    rationale=m.rationale,
                    confidence_score=float(m.confidence_score),
                    created_at=m.created_at,
                    requirement_code=row.requirement_code,
                    requirement_title=row.requirement_title,
                    category=row.category,
                    framework_name=row.framework_name,
                )
            )

        # Audit History (joined with User)
        hist = db.execute(
            select(ThreatAuditHistory, User.full_name.label("reviewer_name"))
            .outerjoin(User, User.id == ThreatAuditHistory.reviewer_id)
            .where(ThreatAuditHistory.threat_id == threat.id)
            .order_by(ThreatAuditHistory.created_at.desc())
        ).all()

        hist_responses: List[ThreatAuditHistoryResponse] = []
        for row in hist:
            h = row[0]
            hist_responses.append(
                ThreatAuditHistoryResponse(
                    id=h.id,
                    threat_id=h.threat_id,
                    reviewer_id=h.reviewer_id,
                    reviewer_name=row.reviewer_name,
                    action=h.action,
                    previous_status=h.previous_status,
                    new_status=h.new_status,
                    changes=h.changes,
                    reason=h.reason,
                    created_at=h.created_at,
                )
            )

        return ThreatDetailResponse(
            id=threat.id,
            audit_id=threat.audit_id,
            threat_analysis_run_id=threat.threat_analysis_run_id,
            threat_title=threat.threat_title,
            threat_description=threat.threat_description,
            stride_category=threat.stride_category,
            threat_category=threat.threat_category,
            attack_objective=threat.attack_objective,
            attack_vector=threat.attack_vector,
            entry_point=threat.entry_point,
            preconditions=threat.preconditions,
            attack_steps=threat.attack_steps,
            target_assets=threat.target_assets,
            affected_components=threat.affected_components,
            trust_boundaries_crossed=threat.trust_boundaries_crossed,
            potential_consequences=threat.potential_consequences,
            cia_confidentiality=threat.cia_confidentiality,
            cia_integrity=threat.cia_integrity,
            cia_availability=threat.cia_availability,
            likelihood_score=threat.likelihood_score,
            likelihood_rationale=threat.likelihood_rationale,
            impact_score=threat.impact_score,
            impact_rationale=threat.impact_rationale,
            risk_score=threat.risk_score,
            severity=threat.severity,
            is_provisional=threat.is_provisional,
            confidence_score=float(threat.confidence_score),
            review_status=threat.review_status,
            review_reason=threat.review_reason,
            reviewed_at=threat.reviewed_at,
            assumptions=threat.assumptions,
            missing_information=threat.missing_information,
            threat_metadata=threat.threat_metadata,
            mapped_requirements_count=len(map_responses),
            attack_nodes_count=len(node_responses),
            attack_path_nodes=node_responses,
            evidence_references=ev_responses,
            requirement_mappings=map_responses,
            audit_history=hist_responses,
            created_at=threat.created_at,
            updated_at=threat.updated_at,
        )

    @classmethod
    def accept_threat(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        threat_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> Threat:
        """Accepts a threat scenario as valid and applicable."""
        cls._verify_audit(db, organization_id, audit_id)
        threat = db.execute(
            select(Threat).where(Threat.id == threat_id, Threat.audit_id == audit_id)
        ).scalar_one_or_none()
        if not threat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat not found.")

        prev_status = threat.review_status
        threat.review_status = "accepted"
        threat.review_reason = reason
        threat.reviewed_by = user_id
        threat.reviewed_at = datetime.now(timezone.utc)

        # Log history
        history = ThreatAuditHistory(
            threat_id=threat.id,
            reviewer_id=user_id,
            action="accept",
            previous_status=prev_status,
            new_status="accepted",
            changes={"status": {"old": prev_status, "new": "accepted"}},
            reason=reason or "Threat accepted by human auditor.",
        )
        db.add(history)
        db.commit()
        db.refresh(threat)
        return threat

    @classmethod
    def reject_threat(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        threat_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> Threat:
        """Rejects a threat scenario with a mandatory reason."""
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A justification reason is required when rejecting a threat.",
            )

        cls._verify_audit(db, organization_id, audit_id)
        threat = db.execute(
            select(Threat).where(Threat.id == threat_id, Threat.audit_id == audit_id)
        ).scalar_one_or_none()
        if not threat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat not found.")

        prev_status = threat.review_status
        threat.review_status = "rejected"
        threat.review_reason = reason.strip()
        threat.reviewed_by = user_id
        threat.reviewed_at = datetime.now(timezone.utc)

        history = ThreatAuditHistory(
            threat_id=threat.id,
            reviewer_id=user_id,
            action="reject",
            previous_status=prev_status,
            new_status="rejected",
            changes={"status": {"old": prev_status, "new": "rejected"}},
            reason=reason.strip(),
        )
        db.add(history)
        db.commit()
        db.refresh(threat)
        return threat

    @classmethod
    def request_review_for_threat(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        threat_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
    ) -> Threat:
        """Flags threat as needing more architectural evidence or clarification."""
        cls._verify_audit(db, organization_id, audit_id)
        threat = db.execute(
            select(Threat).where(Threat.id == threat_id, Threat.audit_id == audit_id)
        ).scalar_one_or_none()
        if not threat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat not found.")

        prev_status = threat.review_status
        threat.review_status = "needs_more_information"
        threat.review_reason = reason
        threat.reviewed_by = user_id
        threat.reviewed_at = datetime.now(timezone.utc)

        history = ThreatAuditHistory(
            threat_id=threat.id,
            reviewer_id=user_id,
            action="request_more_information",
            previous_status=prev_status,
            new_status="needs_more_information",
            changes={"status": {"old": prev_status, "new": "needs_more_information"}},
            reason=reason or "Additional architectural evidence requested.",
        )
        db.add(history)
        db.commit()
        db.refresh(threat)
        return threat

    @classmethod
    def edit_threat(
        cls,
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        threat_id: UUID,
        user_id: UUID,
        req: ThreatEditRequest,
    ) -> Threat:
        """Auditor modifies threat scenario parameters with full audit trail."""
        cls._verify_audit(db, organization_id, audit_id)
        threat = db.execute(
            select(Threat).where(Threat.id == threat_id, Threat.audit_id == audit_id)
        ).scalar_one_or_none()
        if not threat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat not found.")

        prev_status = threat.review_status
        changes: Dict[str, Any] = {}

        if req.threat_title is not None and req.threat_title != threat.threat_title:
            changes["threat_title"] = {"old": threat.threat_title, "new": req.threat_title}
            threat.threat_title = req.threat_title

        if req.threat_description is not None and req.threat_description != threat.threat_description:
            changes["threat_description"] = {"old": threat.threat_description, "new": req.threat_description}
            threat.threat_description = req.threat_description

        if req.stride_category is not None and req.stride_category != threat.stride_category:
            changes["stride_category"] = {"old": threat.stride_category, "new": req.stride_category}
            threat.stride_category = req.stride_category
            threat.threat_category = req.stride_category

        if req.attack_objective is not None and req.attack_objective != threat.attack_objective:
            changes["attack_objective"] = {"old": threat.attack_objective, "new": req.attack_objective}
            threat.attack_objective = req.attack_objective

        if req.attack_vector is not None and req.attack_vector != threat.attack_vector:
            changes["attack_vector"] = {"old": threat.attack_vector, "new": req.attack_vector}
            threat.attack_vector = req.attack_vector

        if req.entry_point is not None and req.entry_point != threat.entry_point:
            changes["entry_point"] = {"old": threat.entry_point, "new": req.entry_point}
            threat.entry_point = req.entry_point

        if req.preconditions is not None and req.preconditions != threat.preconditions:
            changes["preconditions"] = {"old": threat.preconditions, "new": req.preconditions}
            threat.preconditions = req.preconditions

        if req.attack_steps is not None and req.attack_steps != threat.attack_steps:
            changes["attack_steps"] = {"old": threat.attack_steps, "new": req.attack_steps}
            threat.attack_steps = req.attack_steps

        # Scoring recalculations
        new_likelihood = req.likelihood_score if req.likelihood_score is not None else threat.likelihood_score
        new_impact = req.impact_score if req.impact_score is not None else threat.impact_score

        if req.likelihood_score is not None and req.likelihood_score != threat.likelihood_score:
            changes["likelihood_score"] = {"old": threat.likelihood_score, "new": req.likelihood_score}
            threat.likelihood_score = req.likelihood_score

        if req.impact_score is not None and req.impact_score != threat.impact_score:
            changes["impact_score"] = {"old": threat.impact_score, "new": req.impact_score}
            threat.impact_score = req.impact_score

        if req.likelihood_score is not None or req.impact_score is not None:
            new_risk, new_severity = compute_risk_and_severity(new_likelihood, new_impact)
            if new_risk != threat.risk_score:
                changes["risk_score"] = {"old": threat.risk_score, "new": new_risk}
                threat.risk_score = new_risk
            if new_severity != threat.severity:
                changes["severity"] = {"old": threat.severity, "new": new_severity}
                threat.severity = new_severity

        if req.cia_confidentiality is not None and req.cia_confidentiality != threat.cia_confidentiality:
            changes["cia_confidentiality"] = {"old": threat.cia_confidentiality, "new": req.cia_confidentiality}
            threat.cia_confidentiality = req.cia_confidentiality

        if req.cia_integrity is not None and req.cia_integrity != threat.cia_integrity:
            changes["cia_integrity"] = {"old": threat.cia_integrity, "new": req.cia_integrity}
            threat.cia_integrity = req.cia_integrity

        if req.cia_availability is not None and req.cia_availability != threat.cia_availability:
            changes["cia_availability"] = {"old": threat.cia_availability, "new": req.cia_availability}
            threat.cia_availability = req.cia_availability

        if req.is_provisional is not None and req.is_provisional != threat.is_provisional:
            changes["is_provisional"] = {"old": threat.is_provisional, "new": req.is_provisional}
            threat.is_provisional = req.is_provisional

        threat.review_status = "edited"
        threat.reviewed_by = user_id
        threat.reviewed_at = datetime.now(timezone.utc)
        threat.review_reason = req.reason

        history = ThreatAuditHistory(
            threat_id=threat.id,
            reviewer_id=user_id,
            action="edit",
            previous_status=prev_status,
            new_status="edited",
            changes=changes,
            reason=req.reason or "Auditor updated threat parameters.",
        )
        db.add(history)
        db.commit()
        db.refresh(threat)
        return threat

    @classmethod
    def get_attack_path(
        cls, db: Session, organization_id: UUID, audit_id: UUID, threat_id: UUID
    ) -> List[AttackPathNode]:
        """Retrieves structured attack tree nodes for a threat."""
        cls._verify_audit(db, organization_id, audit_id)
        nodes = db.execute(
            select(AttackPathNode)
            .where(
                AttackPathNode.threat_id == threat_id,
                AttackPathNode.organization_id == organization_id,
                AttackPathNode.audit_id == audit_id,
            )
            .order_by(AttackPathNode.sequence_number.asc())
        ).scalars().all()
        return list(nodes)

    @classmethod
    def get_threat_requirements(
        cls, db: Session, organization_id: UUID, audit_id: UUID, threat_id: UUID
    ) -> List[ThreatRequirementMappingResponse]:
        """Retrieves mapped approved regulatory requirements for a threat."""
        cls._verify_audit(db, organization_id, audit_id)
        maps = db.execute(
            select(
                ThreatRequirementMapping,
                Requirement.requirement_code,
                Requirement.title.label("requirement_title"),
                Requirement.category,
                func.coalesce(RegulatoryFramework.name, Requirement.framework).label("framework_name"),
            )
            .join(Requirement, Requirement.id == ThreatRequirementMapping.requirement_id)
            .outerjoin(RegulatoryFramework, RegulatoryFramework.id == Requirement.framework_id)
            .where(
                ThreatRequirementMapping.threat_id == threat_id,
                ThreatRequirementMapping.organization_id == organization_id,
                ThreatRequirementMapping.audit_id == audit_id,
            )
            .order_by(ThreatRequirementMapping.created_at.asc())
        ).all()

        results: List[ThreatRequirementMappingResponse] = []
        for row in maps:
            m = row[0]
            results.append(
                ThreatRequirementMappingResponse(
                    id=m.id,
                    threat_id=m.threat_id,
                    requirement_id=m.requirement_id,
                    relationship_type=m.relationship_type,
                    rationale=m.rationale,
                    confidence_score=float(m.confidence_score),
                    created_at=m.created_at,
                    requirement_code=row.requirement_code,
                    requirement_title=row.requirement_title,
                    category=row.category,
                    framework_name=row.framework_name,
                )
            )
        return results
