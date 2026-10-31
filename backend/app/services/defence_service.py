"""Defence Auditor management service for control discovery, gap analysis, and human review."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.assessments import ControlAssessment, Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.defence import (
    ControlAuditHistory,
    ControlEvidenceReference,
    ControlRequirementMapping,
    ControlThreatMapping,
    DefenceAnalysisRun,
    DiscoveredControl,
    FindingAuditHistory,
    FindingControl,
)
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import Finding
from app.database.models.identity import User
from app.database.models.regulatory import AuditRequirement
from app.schemas.defence import (
    ControlAssessmentResponse,
    ControlAuditHistoryResponse,
    ControlDetailResponse,
    ControlEditRequest,
    ControlEvidenceReferenceResponse,
    ControlRequirementMappingResponse,
    ControlReviewActionRequest,
    ControlThreatMappingResponse,
    DefenceReadinessResponse,
    DiscoveredControlResponse,
    FindingAuditHistoryResponse,
    FindingDetailResponse,
    FindingEditRequest,
    FindingResponse,
    FindingReviewActionRequest,
)
from app.services.defence_auditor import DefenceAuditorService, compute_finding_risk_and_severity

logger = logging.getLogger(__name__)


class DefenceService:
    """Service handling Defence Auditor operations, control inventory, and human reviews."""

    @staticmethod
    def check_readiness(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
    ) -> DefenceReadinessResponse:
        """Evaluates whether an audit has the prerequisite evidence and data for Defence Auditor."""
        audit = db.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        ).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {audit_id} not found.")

        # Evidence documents & chunks
        docs_count = db.execute(
            select(func.count(AuditDocument.id)).where(
                AuditDocument.audit_id == audit_id,
                AuditDocument.organization_id == organization_id,
            )
        ).scalar() or 0

        chunks_count = 0
        if docs_count > 0:
            doc_subq = select(AuditDocument.id).where(
                AuditDocument.audit_id == audit_id,
                AuditDocument.organization_id == organization_id,
            )
            chunks_count = db.execute(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.audit_document_id.in_(doc_subq))
            ).scalar() or 0

        # Approved & applicable regulatory requirements
        approved_reqs = db.execute(
            select(func.count(Requirement.id))
            .join(AuditRequirement, AuditRequirement.requirement_id == Requirement.id)
            .where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.organization_id == organization_id,
                AuditRequirement.applicability_status == "applicable",
                Requirement.review_status == "approved",
            )
        ).scalar() or 0

        # Threat scenarios
        threat_rows = db.execute(
            select(Threat.review_status, func.count(Threat.id))
            .where(Threat.audit_id == audit_id, Threat.organization_id == organization_id)
            .group_by(Threat.review_status)
        ).all()

        threat_counts = {r[0]: r[1] for r in threat_rows}
        accepted_threats = threat_counts.get("accepted", 0)
        pending_threats = threat_counts.get("pending_review", 0)
        rejected_threats = threat_counts.get("rejected", 0)

        blockers: List[str] = []
        warnings: List[str] = []

        if docs_count == 0 or chunks_count == 0:
            blockers.append("No audit evidence documents or text chunks found. Please upload audit documents before running Defence Auditor.")
        if approved_reqs == 0 and (accepted_threats + pending_threats) == 0:
            blockers.append("No approved regulatory requirements or eligible threat scenarios found. Please approve requirements or generate threats first.")

        if pending_threats > 0:
            warnings.append(f"{pending_threats} threat scenarios are still pending review. These will be evaluated as provisional in control assessments.")
        if docs_count == 1:
            warnings.append("Only 1 evidence document provided. Expanding evidence documentation improves evaluation coverage.")

        is_ready = len(blockers) == 0

        return DefenceReadinessResponse(
            is_ready=is_ready,
            total_documents=docs_count,
            approved_requirements=approved_reqs,
            accepted_threats=accepted_threats,
            pending_threats=pending_threats,
            rejected_threats=rejected_threats,
            blockers=blockers,
            warnings=warnings,
        )

    @staticmethod
    def create_analysis_run(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        model_name: Optional[str] = None,
    ) -> DefenceAnalysisRun:
        """Initializes a new Defence Analysis run after readiness verification."""
        readiness = DefenceService.check_readiness(db, organization_id, audit_id)
        if not readiness.is_ready:
            raise ValueError(f"Audit not ready for defence analysis: {'; '.join(readiness.blockers)}")

        run = DefenceAnalysisRun(
            organization_id=organization_id,
            audit_id=audit_id,
            status="pending",
            model_name=model_name or "gemini-1.5-flash",
            prompt_version="v1.0",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def list_analysis_runs(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
    ) -> List[DefenceAnalysisRun]:
        return list(
            db.execute(
                select(DefenceAnalysisRun)
                .where(
                    DefenceAnalysisRun.organization_id == organization_id,
                    DefenceAnalysisRun.audit_id == audit_id,
                )
                .order_by(DefenceAnalysisRun.created_at.desc())
            ).scalars().all()
        )

    @staticmethod
    def get_analysis_run(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        run_id: UUID,
    ) -> Optional[DefenceAnalysisRun]:
        return db.execute(
            select(DefenceAnalysisRun).where(
                DefenceAnalysisRun.id == run_id,
                DefenceAnalysisRun.audit_id == audit_id,
                DefenceAnalysisRun.organization_id == organization_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def list_controls(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        category: Optional[str] = None,
        maturity: Optional[str] = None,
        implementation_status: Optional[str] = None,
        operational_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[DiscoveredControlResponse]:
        """Lists discovered controls with optional filtering and summary metrics."""
        query = select(DiscoveredControl).where(
            DiscoveredControl.organization_id == organization_id,
            DiscoveredControl.audit_id == audit_id,
        )

        if category:
            query = query.where(DiscoveredControl.category.ilike(f"%{category}%"))
        if maturity:
            query = query.where(DiscoveredControl.evidence_maturity == maturity)
        if implementation_status:
            query = query.where(DiscoveredControl.implementation_status == implementation_status)
        if operational_status:
            query = query.where(DiscoveredControl.operational_status == operational_status)
        if search:
            s = f"%{search}%"
            query = query.where(
                or_(
                    DiscoveredControl.name.ilike(s),
                    DiscoveredControl.description.ilike(s),
                    DiscoveredControl.control_code.ilike(s),
                    DiscoveredControl.category.ilike(s),
                )
            )

        query = query.order_by(DiscoveredControl.control_code.asc())
        controls = list(db.execute(query).scalars().all())

        results = []
        for c in controls:
            req_cnt = db.execute(
                select(func.count(ControlRequirementMapping.id)).where(ControlRequirementMapping.control_id == c.id)
            ).scalar() or 0
            thr_cnt = db.execute(
                select(func.count(ControlThreatMapping.id)).where(ControlThreatMapping.control_id == c.id)
            ).scalar() or 0
            ev_cnt = db.execute(
                select(func.count(ControlEvidenceReference.id)).where(ControlEvidenceReference.control_id == c.id)
            ).scalar() or 0

            # Primary assessment
            primary_assess = db.execute(
                select(ControlAssessment)
                .where(ControlAssessment.control_id == c.id)
                .order_by(ControlAssessment.created_at.desc())
            ).scalars().first()

            resp = DiscoveredControlResponse(
                id=c.id,
                organization_id=c.organization_id,
                audit_id=c.audit_id,
                defence_analysis_run_id=c.defence_analysis_run_id,
                control_code=c.control_code,
                name=c.name,
                description=c.description,
                category=c.category,
                control_objective=c.control_objective,
                implementation_status=c.implementation_status,
                operational_status=c.operational_status,
                evidence_maturity=c.evidence_maturity,
                confidence_score=float(c.confidence_score),
                created_at=c.created_at,
                updated_at=c.updated_at,
                assessment_status=primary_assess.status if primary_assess else None,
                assessment_explanation=primary_assess.assessment_explanation if primary_assess else None,
                requirement_count=req_cnt,
                threat_count=thr_cnt,
                evidence_count=ev_cnt,
            )
            results.append(resp)

        return results

    @staticmethod
    def get_control_detail(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        control_id: UUID,
    ) -> Optional[ControlDetailResponse]:
        """Fetches full control detail with assessments, mappings, citations, and history."""
        control = db.execute(
            select(DiscoveredControl).where(
                DiscoveredControl.id == control_id,
                DiscoveredControl.audit_id == audit_id,
                DiscoveredControl.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not control:
            return None

        # Assessments
        assessments = list(
            db.execute(
                select(ControlAssessment)
                .where(ControlAssessment.control_id == control_id)
                .order_by(ControlAssessment.created_at.desc())
            ).scalars().all()
        )

        # Requirement Mappings
        req_maps = list(
            db.execute(
                select(ControlRequirementMapping)
                .where(ControlRequirementMapping.control_id == control_id)
                .order_by(ControlRequirementMapping.created_at.asc())
            ).scalars().all()
        )
        req_responses = []
        for rm in req_maps:
            req_obj = db.execute(select(Requirement).where(Requirement.id == rm.requirement_id)).scalar_one_or_none()
            req_responses.append(
                ControlRequirementMappingResponse(
                    id=rm.id,
                    control_id=rm.control_id,
                    requirement_id=rm.requirement_id,
                    coverage_level=rm.coverage_level,
                    mapping_rationale=rm.mapping_rationale,
                    confidence_score=float(rm.confidence_score),
                    review_status=rm.review_status,
                    requirement_identifier=req_obj.identifier or req_obj.requirement_code if req_obj else None,
                    requirement_statement=req_obj.requirement_statement or req_obj.description if req_obj else None,
                )
            )

        # Threat Mappings
        threat_maps = list(
            db.execute(
                select(ControlThreatMapping)
                .where(ControlThreatMapping.control_id == control_id)
                .order_by(ControlThreatMapping.created_at.asc())
            ).scalars().all()
        )
        threat_responses = []
        for tm in threat_maps:
            threat_obj = db.execute(select(Threat).where(Threat.id == tm.threat_id)).scalar_one_or_none()
            threat_responses.append(
                ControlThreatMappingResponse(
                    id=tm.id,
                    control_id=tm.control_id,
                    threat_id=tm.threat_id,
                    mitigation_level=tm.mitigation_level,
                    mapping_rationale=tm.mapping_rationale,
                    confidence_score=float(tm.confidence_score),
                    review_status=tm.review_status,
                    threat_title=threat_obj.title if threat_obj else None,
                    threat_severity=threat_obj.severity if threat_obj else None,
                )
            )

        # Evidence references
        ev_refs = list(
            db.execute(
                select(ControlEvidenceReference)
                .where(ControlEvidenceReference.control_id == control_id)
                .order_by(ControlEvidenceReference.created_at.asc())
            ).scalars().all()
        )

        # Audit History
        history = list(
            db.execute(
                select(ControlAuditHistory)
                .where(ControlAuditHistory.control_id == control_id)
                .order_by(ControlAuditHistory.created_at.desc())
            ).scalars().all()
        )
        history_responses = []
        for h in history:
            reviewer = db.execute(select(User).where(User.id == h.reviewer_id)).scalar_one_or_none() if h.reviewer_id else None
            history_responses.append(
                ControlAuditHistoryResponse(
                    id=h.id,
                    control_id=h.control_id,
                    assessment_id=h.assessment_id,
                    reviewer_id=h.reviewer_id,
                    reviewer_email=reviewer.email if reviewer else None,
                    action=h.action,
                    previous_status=h.previous_status,
                    new_status=h.new_status,
                    changes=h.changes,
                    reason=h.reason,
                    created_at=h.created_at,
                )
            )

        primary_assess = assessments[0] if assessments else None

        return ControlDetailResponse(
            id=control.id,
            organization_id=control.organization_id,
            audit_id=control.audit_id,
            defence_analysis_run_id=control.defence_analysis_run_id,
            control_code=control.control_code,
            name=control.name,
            description=control.description,
            category=control.category,
            control_objective=control.control_objective,
            implementation_status=control.implementation_status,
            operational_status=control.operational_status,
            evidence_maturity=control.evidence_maturity,
            confidence_score=float(control.confidence_score),
            created_at=control.created_at,
            updated_at=control.updated_at,
            assessment_status=primary_assess.status if primary_assess else None,
            assessment_explanation=primary_assess.assessment_explanation if primary_assess else None,
            requirement_count=len(req_responses),
            threat_count=len(threat_responses),
            evidence_count=len(ev_refs),
            assessments=[ControlAssessmentResponse.model_validate(a) for a in assessments],
            requirement_mappings=req_responses,
            threat_mappings=threat_responses,
            evidence_references=[ControlEvidenceReferenceResponse.model_validate(e) for e in ev_refs],
            audit_history=history_responses,
        )

    @staticmethod
    def review_control(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        control_id: UUID,
        reviewer: User,
        payload: ControlReviewActionRequest,
    ) -> DiscoveredControl:
        """Processes human review action (approve, reject, request_more_information, reassess) on a control."""
        control = db.execute(
            select(DiscoveredControl).where(
                DiscoveredControl.id == control_id,
                DiscoveredControl.audit_id == audit_id,
                DiscoveredControl.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not control:
            raise ValueError(f"Control {control_id} not found.")

        action = payload.action
        if action not in ("approve", "reject", "request_more_information", "reassess"):
            raise ValueError(f"Invalid review action: {action}")

        if action == "reject" and not (payload.reason and payload.reason.strip()):
            raise ValueError("A documented reason is mandatory when rejecting a control or assessment.")

        # Update primary assessment review status
        primary_assess = db.execute(
            select(ControlAssessment)
            .where(ControlAssessment.control_id == control_id)
            .order_by(ControlAssessment.created_at.desc())
        ).scalars().first()

        prev_status = primary_assess.review_status if primary_assess else "pending_review"
        new_status = {
            "approve": "approved",
            "reject": "rejected",
            "request_more_information": "needs_more_information",
            "reassess": "pending_review",
        }[action]

        if primary_assess:
            primary_assess.review_status = new_status
            primary_assess.reviewed_by = reviewer.id
            primary_assess.reviewed_at = datetime.now(timezone.utc)
            primary_assess.review_reason = payload.reason

        history = ControlAuditHistory(
            control_id=control.id,
            assessment_id=primary_assess.id if primary_assess else None,
            reviewer_id=reviewer.id,
            action=action,
            previous_status=prev_status,
            new_status=new_status,
            changes={"action": action, "review_status": new_status},
            reason=payload.reason,
        )
        db.add(history)
        db.commit()
        db.refresh(control)
        return control

    @staticmethod
    def edit_control(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        control_id: UUID,
        reviewer: User,
        payload: ControlEditRequest,
    ) -> DiscoveredControl:
        """Applies manual edits to control details or assessment status, logging audit trail."""
        control = db.execute(
            select(DiscoveredControl).where(
                DiscoveredControl.id == control_id,
                DiscoveredControl.audit_id == audit_id,
                DiscoveredControl.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not control:
            raise ValueError(f"Control {control_id} not found.")

        changes: Dict[str, Any] = {}
        if payload.name and payload.name != control.name:
            changes["name"] = {"old": control.name, "new": payload.name}
            control.name = payload.name
        if payload.description and payload.description != control.description:
            changes["description"] = {"old": control.description, "new": payload.description}
            control.description = payload.description
        if payload.category and payload.category != control.category:
            changes["category"] = {"old": control.category, "new": payload.category}
            control.category = payload.category
        if payload.implementation_status and payload.implementation_status != control.implementation_status:
            changes["implementation_status"] = {"old": control.implementation_status, "new": payload.implementation_status}
            control.implementation_status = payload.implementation_status
        if payload.operational_status and payload.operational_status != control.operational_status:
            changes["operational_status"] = {"old": control.operational_status, "new": payload.operational_status}
            control.operational_status = payload.operational_status
        if payload.evidence_maturity and payload.evidence_maturity != control.evidence_maturity:
            changes["evidence_maturity"] = {"old": control.evidence_maturity, "new": payload.evidence_maturity}
            control.evidence_maturity = payload.evidence_maturity

        # Primary assessment edits
        primary_assess = db.execute(
            select(ControlAssessment)
            .where(ControlAssessment.control_id == control_id)
            .order_by(ControlAssessment.created_at.desc())
        ).scalars().first()

        if primary_assess:
            if payload.assessment_status and payload.assessment_status != primary_assess.status:
                changes["assessment_status"] = {"old": primary_assess.status, "new": payload.assessment_status}
                primary_assess.status = payload.assessment_status
            if payload.assessment_explanation and payload.assessment_explanation != primary_assess.assessment_explanation:
                changes["assessment_explanation"] = {"old": primary_assess.assessment_explanation, "new": payload.assessment_explanation}
                primary_assess.assessment_explanation = payload.assessment_explanation
                primary_assess.rationale = payload.assessment_explanation
            primary_assess.review_status = "edited"
            primary_assess.reviewed_by = reviewer.id
            primary_assess.reviewed_at = datetime.now(timezone.utc)

        history = ControlAuditHistory(
            control_id=control.id,
            assessment_id=primary_assess.id if primary_assess else None,
            reviewer_id=reviewer.id,
            action="edit",
            previous_status="pending_review",
            new_status="edited",
            changes=changes,
            reason=payload.reason,
        )
        db.add(history)
        db.commit()
        db.refresh(control)
        return control

    @staticmethod
    def list_findings(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        evidence_state: Optional[str] = None,
        review_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[FindingResponse]:
        """Lists findings and security gaps for an audit."""
        query = select(Finding).where(
            Finding.organization_id == organization_id,
            Finding.audit_id == audit_id,
        )

        if category:
            query = query.where(Finding.finding_category == category)
        if severity:
            query = query.where(Finding.severity == severity)
        if evidence_state:
            query = query.where(Finding.evidence_state == evidence_state)
        if review_status:
            query = query.where(Finding.review_status == review_status)
        if search:
            s = f"%{search}%"
            query = query.where(
                or_(
                    Finding.title.ilike(s),
                    Finding.description.ilike(s),
                    Finding.finding_code.ilike(s),
                )
            )

        query = query.order_by(Finding.risk_score.desc().nullslast(), Finding.created_at.desc())
        findings = list(db.execute(query).scalars().all())

        results = []
        for f in findings:
            # Related controls
            links = list(
                db.execute(
                    select(FindingControl).where(FindingControl.finding_id == f.id)
                ).scalars().all()
            )
            ctrl_codes = []
            for link in links:
                c = db.execute(select(DiscoveredControl).where(DiscoveredControl.id == link.control_id)).scalar_one_or_none()
                if c:
                    ctrl_codes.append(c.control_code)

            resp = FindingResponse(
                id=f.id,
                organization_id=f.organization_id,
                audit_id=f.audit_id,
                defence_analysis_run_id=f.defence_analysis_run_id,
                finding_code=f.finding_code,
                title=f.title,
                description=f.description,
                severity=f.severity,
                evidence_state=f.evidence_state,
                finding_category=f.finding_category,
                likelihood_score=f.likelihood_score,
                impact_score=f.impact_score,
                risk_score=f.risk_score,
                is_provisional=f.is_provisional,
                confidence_score=float(f.confidence_score) if f.confidence_score is not None else None,
                remediation_recommendation=f.remediation_recommendation or f.remediation_guidance,
                review_status=f.review_status,
                review_reason=f.review_reason,
                reviewed_by=f.reviewed_by,
                reviewed_at=f.reviewed_at,
                created_at=f.created_at,
                updated_at=f.updated_at,
                related_control_codes=ctrl_codes,
            )
            results.append(resp)

        return results

    @staticmethod
    def get_finding_detail(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        finding_id: UUID,
    ) -> Optional[FindingDetailResponse]:
        """Fetches complete finding detail with linked controls and immutable review history."""
        finding = db.execute(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.audit_id == audit_id,
                Finding.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not finding:
            return None

        # Linked controls
        links = list(
            db.execute(
                select(FindingControl).where(FindingControl.finding_id == finding_id)
            ).scalars().all()
        )
        related_controls = []
        ctrl_codes = []
        for link in links:
            c = db.execute(select(DiscoveredControl).where(DiscoveredControl.id == link.control_id)).scalar_one_or_none()
            if c:
                ctrl_codes.append(c.control_code)
                related_controls.append(
                    DiscoveredControlResponse(
                        id=c.id,
                        organization_id=c.organization_id,
                        audit_id=c.audit_id,
                        defence_analysis_run_id=c.defence_analysis_run_id,
                        control_code=c.control_code,
                        name=c.name,
                        description=c.description,
                        category=c.category,
                        control_objective=c.control_objective,
                        implementation_status=c.implementation_status,
                        operational_status=c.operational_status,
                        evidence_maturity=c.evidence_maturity,
                        confidence_score=float(c.confidence_score),
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                )

        # Audit history
        histories = list(
            db.execute(
                select(FindingAuditHistory)
                .where(FindingAuditHistory.finding_id == finding_id)
                .order_by(FindingAuditHistory.created_at.desc())
            ).scalars().all()
        )
        hist_responses = []
        for h in histories:
            reviewer = db.execute(select(User).where(User.id == h.reviewer_id)).scalar_one_or_none() if h.reviewer_id else None
            hist_responses.append(
                FindingAuditHistoryResponse(
                    id=h.id,
                    finding_id=h.finding_id,
                    reviewer_id=h.reviewer_id,
                    reviewer_email=reviewer.email if reviewer else None,
                    action=h.action,
                    previous_status=h.previous_status,
                    new_status=h.new_status,
                    changes=h.changes,
                    reason=h.reason,
                    created_at=h.created_at,
                )
            )

        return FindingDetailResponse(
            id=finding.id,
            organization_id=finding.organization_id,
            audit_id=finding.audit_id,
            defence_analysis_run_id=finding.defence_analysis_run_id,
            finding_code=finding.finding_code,
            title=finding.title,
            description=finding.description,
            severity=finding.severity,
            evidence_state=finding.evidence_state,
            finding_category=finding.finding_category,
            likelihood_score=finding.likelihood_score,
            impact_score=finding.impact_score,
            risk_score=finding.risk_score,
            is_provisional=finding.is_provisional,
            confidence_score=float(finding.confidence_score) if finding.confidence_score is not None else None,
            remediation_recommendation=finding.remediation_recommendation or finding.remediation_guidance,
            review_status=finding.review_status,
            review_reason=finding.review_reason,
            reviewed_by=finding.reviewed_by,
            reviewed_at=finding.reviewed_at,
            created_at=finding.created_at,
            updated_at=finding.updated_at,
            related_control_codes=ctrl_codes,
            related_controls=related_controls,
            audit_history=hist_responses,
        )

    @staticmethod
    def review_finding(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        finding_id: UUID,
        reviewer: User,
        payload: FindingReviewActionRequest,
    ) -> Finding:
        """Handles human review action (approve, reject, request_more_information, reassess) on a finding."""
        finding = db.execute(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.audit_id == audit_id,
                Finding.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not finding:
            raise ValueError(f"Finding {finding_id} not found.")

        action = payload.action
        if action not in ("approve", "reject", "request_more_information", "reassess"):
            raise ValueError(f"Invalid review action: {action}")

        if action == "reject" and not (payload.reason and payload.reason.strip()):
            raise ValueError("A documented reason is mandatory when rejecting a finding.")

        prev_status = finding.review_status
        new_status = {
            "approve": "approved",
            "reject": "rejected",
            "request_more_information": "needs_more_information",
            "reassess": "pending_review",
        }[action]

        finding.review_status = new_status
        finding.reviewed_by = reviewer.id
        finding.reviewed_at = datetime.now(timezone.utc)
        finding.review_reason = payload.reason

        history = FindingAuditHistory(
            finding_id=finding.id,
            reviewer_id=reviewer.id,
            action=action,
            previous_status=prev_status,
            new_status=new_status,
            changes={"action": action, "review_status": new_status},
            reason=payload.reason,
        )
        db.add(history)
        db.commit()
        db.refresh(finding)
        return finding

    @staticmethod
    def edit_finding(
        db: Session,
        organization_id: UUID,
        audit_id: UUID,
        finding_id: UUID,
        reviewer: User,
        payload: FindingEditRequest,
    ) -> Finding:
        """Applies manual edits to finding details, deterministically recomputing risk score if likelihood/impact changes."""
        finding = db.execute(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.audit_id == audit_id,
                Finding.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not finding:
            raise ValueError(f"Finding {finding_id} not found.")

        changes: Dict[str, Any] = {}
        if payload.title and payload.title != finding.title:
            changes["title"] = {"old": finding.title, "new": payload.title}
            finding.title = payload.title
        if payload.description and payload.description != finding.description:
            changes["description"] = {"old": finding.description, "new": payload.description}
            finding.description = payload.description
        if payload.finding_category and payload.finding_category != finding.finding_category:
            changes["finding_category"] = {"old": finding.finding_category, "new": payload.finding_category}
            finding.finding_category = payload.finding_category
        if payload.remediation_recommendation:
            changes["remediation_recommendation"] = {"old": finding.remediation_recommendation, "new": payload.remediation_recommendation}
            finding.remediation_recommendation = payload.remediation_recommendation
            finding.remediation_guidance = payload.remediation_recommendation

        # Score recalculation
        recalc = False
        if payload.likelihood_score is not None and payload.likelihood_score != finding.likelihood_score:
            changes["likelihood_score"] = {"old": finding.likelihood_score, "new": payload.likelihood_score}
            finding.likelihood_score = payload.likelihood_score
            recalc = True
        if payload.impact_score is not None and payload.impact_score != finding.impact_score:
            changes["impact_score"] = {"old": finding.impact_score, "new": payload.impact_score}
            finding.impact_score = payload.impact_score
            recalc = True

        if recalc and finding.likelihood_score and finding.impact_score:
            new_risk, new_sev = compute_finding_risk_and_severity(finding.likelihood_score, finding.impact_score)
            changes["risk_score"] = {"old": finding.risk_score, "new": new_risk}
            changes["severity"] = {"old": finding.severity, "new": new_sev}
            finding.risk_score = new_risk
            finding.severity = new_sev

        finding.review_status = "edited"
        finding.reviewed_by = reviewer.id
        finding.reviewed_at = datetime.now(timezone.utc)

        history = FindingAuditHistory(
            finding_id=finding.id,
            reviewer_id=reviewer.id,
            action="edit",
            previous_status="pending_review",
            new_status="edited",
            changes=changes,
            reason=payload.reason,
        )
        db.add(history)
        db.commit()
        db.refresh(finding)
        return finding
