"""Defence Auditor service orchestrating security safeguard evaluation and gap analysis (Milestone 6)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.assessments import ControlAssessment, Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.defence import (
    ControlEvidenceReference,
    ControlRequirementMapping,
    ControlThreatMapping,
    DefenceAnalysisRun,
    DiscoveredControl,
    FindingControl,
)
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import Finding
from app.database.models.regulatory import AuditRequirement
from app.schemas.defence import DefenceAuditorOutput
from app.services.ai.gemini_client import get_gemini_client
from app.services.ai.prompts.defence_auditor import (
    CITATION_TYPES,
    CONTROLLED_ASSESSMENT_STATUSES,
    DEFENCE_AUDITOR_SYSTEM_PROMPT,
    EVIDENCE_MATURITY_LEVELS,
    FINDING_CATEGORIES,
    build_defence_analysis_prompt,
)

logger = logging.getLogger(__name__)


def compute_finding_risk_and_severity(likelihood: int, impact: int) -> Tuple[int, str]:
    """Deterministically computes risk score (L * I) and severity rating."""
    l = max(1, min(5, int(likelihood)))
    i = max(1, min(5, int(impact)))
    score = l * i
    if score <= 4:
        severity = "low"
    elif score <= 9:
        severity = "medium"
    elif score <= 14:
        severity = "high"
    elif score <= 19:
        severity = "very_high"
    else:
        severity = "critical"
    return score, severity


class DefenceAuditorService:
    """Core AI agent engine executing evidence-grounded control evaluation."""

    @staticmethod
    async def run_defence_analysis(db: Session, run_id: UUID) -> DefenceAnalysisRun:
        """Executes full defence evaluation pipeline for a DefenceAnalysisRun."""
        run = db.execute(select(DefenceAnalysisRun).where(DefenceAnalysisRun.id == run_id)).scalar_one_or_none()
        if not run:
            raise ValueError(f"DefenceAnalysisRun {run_id} not found.")

        audit = db.execute(select(Audit).where(Audit.id == run.audit_id)).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {run.audit_id} not found.")

        start_time = time.time()
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            # 1. Gather audit evidence documents and chunks (excluding regulatory framework documents)
            doc_query = select(AuditDocument).where(
                AuditDocument.audit_id == audit.id,
                AuditDocument.organization_id == run.organization_id,
            )
            audit_docs = list(db.execute(doc_query).scalars().all())
            doc_ids = [d.id for d in audit_docs]

            chunks: List[DocumentChunk] = []
            if doc_ids:
                chunks_query = (
                    select(DocumentChunk)
                    .where(DocumentChunk.audit_document_id.in_(doc_ids))
                    .order_by(DocumentChunk.audit_document_id, DocumentChunk.chunk_index)
                )
                chunks = list(db.execute(chunks_query).scalars().all())

            # 2. Gather approved & applicable regulatory requirements
            req_query = (
                select(Requirement, AuditRequirement)
                .join(AuditRequirement, AuditRequirement.requirement_id == Requirement.id)
                .where(
                    AuditRequirement.audit_id == audit.id,
                    AuditRequirement.organization_id == run.organization_id,
                    AuditRequirement.applicability_status == "applicable",
                    Requirement.review_status == "approved",
                )
            )
            approved_req_rows = list(db.execute(req_query).all())
            approved_reqs = [r[0] for r in approved_req_rows]

            # 3. Gather eligible threat scenarios (accepted or pending review; exclude rejected)
            threat_query = select(Threat).where(
                Threat.audit_id == audit.id,
                Threat.organization_id == run.organization_id,
                Threat.review_status != "rejected",
            )
            eligible_threats = list(db.execute(threat_query).scalars().all())

            # Pre-flight readiness validation
            if not chunks:
                raise ValueError("No audit evidence document chunks available for analysis. Please upload and process audit documents first.")
            if not approved_reqs and not eligible_threats:
                raise ValueError("No approved regulatory requirements or eligible threat scenarios found. Please approve requirements or generate threats before running Defence Auditor.")

            # Record inputs
            run.input_document_ids = [str(d.id) for d in audit_docs]
            run.input_requirement_ids = [str(r.id) for r in approved_reqs]
            run.input_threat_ids = [str(t.id) for t in eligible_threats]

            # 4. Prepare serialized payload for AI agent
            system_scope = (
                getattr(audit, "description", None)
                or getattr(audit, "target_system", "Target Enterprise System Boundary")
            )

            req_dicts = []
            for r in approved_reqs:
                req_dicts.append({
                    "id": str(r.id),
                    "identifier": r.identifier or r.requirement_code,
                    "framework": r.framework,
                    "category": r.category,
                    "requirement_statement": r.requirement_statement or r.description,
                    "obligation_type": r.obligation_type,
                })

            threat_dicts = []
            for t in eligible_threats:
                threat_dicts.append({
                    "id": str(t.id),
                    "threat_id_code": t.threat_id_code,
                    "title": t.title,
                    "stride_category": t.stride_category or t.threat_category,
                    "severity": t.severity,
                    "is_provisional": t.review_status == "pending_review",
                    "description": t.description,
                    "target_assets": [],
                })

            doc_map = {d.id: (d.original_filename or d.file_name or "document") for d in audit_docs}
            chunk_dicts = []
            for c in chunks:
                chunk_dicts.append({
                    "id": str(c.id),
                    "document_id": str(c.document_id),
                    "filename": doc_map.get(c.document_id, "document"),
                    "page_number": c.page_start or c.page_number or 1,
                    "section_title": c.section_title,
                    "content": getattr(c, "content", getattr(c, "chunk_text", "")),
                })

            # 5. Build prompt and invoke Gemini Client
            prompt = build_defence_analysis_prompt(
                system_description=system_scope,
                requirements=req_dicts,
                threats=threat_dicts,
                document_chunks=chunk_dicts,
            )

            gemini = get_gemini_client()
            response_json = await gemini.generate_structured(
                prompt=prompt,
                system_instruction=DEFENCE_AUDITOR_SYSTEM_PROMPT,
            )

            # 6. Parse structured output
            output = DefenceAuditorOutput.model_validate(response_json)

            # Map helper lookups
            chunk_by_id: Dict[str, DocumentChunk] = {str(c.id): c for c in chunks}
            req_by_id: Dict[str, Requirement] = {str(r.id): r for r in approved_reqs}
            req_by_code: Dict[str, Requirement] = {
                (r.identifier or r.requirement_code): r for r in approved_reqs if (r.identifier or r.requirement_code)
            }
            threat_by_id: Dict[str, Threat] = {str(t.id): t for t in eligible_threats}
            threat_by_code: Dict[str, Threat] = {t.threat_id_code: t for t in eligible_threats if t.threat_id_code}

            # 7. Persist Discovered Controls and Evidence References
            created_controls_map: Dict[str, DiscoveredControl] = {}
            seq_counter = 1

            for ctrl_item in output.controls:
                ctrl_code = ctrl_item.control_code or f"CTRL-{seq_counter:03d}"
                seq_counter += 1

                # Normalize maturity
                maturity = ctrl_item.evidence_maturity if ctrl_item.evidence_maturity in EVIDENCE_MATURITY_LEVELS else "policy"
                impl_status = ctrl_item.implementation_status if ctrl_item.implementation_status in ("documented", "partially_documented", "undocumented", "unknown") else "documented"
                oper_status = ctrl_item.operational_status if ctrl_item.operational_status in ("active", "planned", "unverified", "unknown") else "unverified"

                # Check existing control in this audit to update or insert
                existing_ctrl = db.execute(
                    select(DiscoveredControl).where(
                        DiscoveredControl.audit_id == audit.id,
                        DiscoveredControl.control_code == ctrl_code,
                    )
                ).scalar_one_or_none()

                if existing_ctrl:
                    discovered_ctrl = existing_ctrl
                    discovered_ctrl.name = ctrl_item.name
                    discovered_ctrl.description = ctrl_item.description
                    discovered_ctrl.category = ctrl_item.category
                    discovered_ctrl.control_objective = ctrl_item.control_objective
                    discovered_ctrl.implementation_status = impl_status
                    discovered_ctrl.operational_status = oper_status
                    discovered_ctrl.evidence_maturity = maturity
                    discovered_ctrl.confidence_score = ctrl_item.confidence_score
                    discovered_ctrl.defence_analysis_run_id = run.id
                else:
                    discovered_ctrl = DiscoveredControl(
                        organization_id=run.organization_id,
                        audit_id=audit.id,
                        defence_analysis_run_id=run.id,
                        control_code=ctrl_code,
                        name=ctrl_item.name,
                        description=ctrl_item.description,
                        category=ctrl_item.category,
                        control_objective=ctrl_item.control_objective,
                        implementation_status=impl_status,
                        operational_status=oper_status,
                        evidence_maturity=maturity,
                        confidence_score=ctrl_item.confidence_score,
                    )
                    db.add(discovered_ctrl)
                db.flush()

                created_controls_map[ctrl_code] = discovered_ctrl

                # Evidence citations for control
                for citation in ctrl_item.evidence_citations:
                    matched_chunk: Optional[DocumentChunk] = None
                    if citation.chunk_id and citation.chunk_id in chunk_by_id:
                        matched_chunk = chunk_by_id[citation.chunk_id]
                    elif chunks:
                        # Fallback to search chunk containing the excerpt
                        for c in chunks:
                            content = getattr(c, "content", getattr(c, "chunk_text", ""))
                            if citation.exact_excerpt and citation.exact_excerpt.lower() in content.lower():
                                matched_chunk = c
                                break
                        if not matched_chunk:
                            matched_chunk = chunks[0]

                    doc_id = matched_chunk.document_id if matched_chunk else audit_docs[0].id
                    doc_filename = doc_map.get(doc_id, citation.filename or "document")

                    cit_type = citation.citation_type if citation.citation_type in CITATION_TYPES else "direct_evidence"
                    cit_maturity = citation.evidence_maturity if citation.evidence_maturity in EVIDENCE_MATURITY_LEVELS else maturity

                    ev_ref = ControlEvidenceReference(
                        organization_id=run.organization_id,
                        audit_id=audit.id,
                        control_id=discovered_ctrl.id,
                        audit_document_id=doc_id,
                        document_chunk_id=matched_chunk.id if matched_chunk else None,
                        original_filename=doc_filename,
                        page_number=citation.page_number or (matched_chunk.page_start if matched_chunk and getattr(matched_chunk, "page_start", None) is not None else (matched_chunk.page_number if matched_chunk else None)) or 1,
                        section_title=citation.section_title or (matched_chunk.section_title if matched_chunk else None),
                        exact_excerpt=citation.exact_excerpt or "Documented control safeguard in provided evidence.",
                        citation_type=cit_type,
                        evidence_maturity=cit_maturity,
                        relevance_explanation=citation.relevance_explanation,
                    )
                    db.add(ev_ref)

                # Mappings to Requirements
                for req_ref in ctrl_item.requirement_ids:
                    target_req = req_by_id.get(req_ref) or req_by_code.get(req_ref)
                    if target_req:
                        existing_map = db.execute(
                            select(ControlRequirementMapping).where(
                                ControlRequirementMapping.control_id == discovered_ctrl.id,
                                ControlRequirementMapping.requirement_id == target_req.id,
                            )
                        ).scalar_one_or_none()
                        if not existing_map:
                            db.add(
                                ControlRequirementMapping(
                                    organization_id=run.organization_id,
                                    audit_id=audit.id,
                                    control_id=discovered_ctrl.id,
                                    requirement_id=target_req.id,
                                    coverage_level="supports",
                                    mapping_rationale=f"Control {discovered_ctrl.control_code} addresses requirement {target_req.identifier or target_req.requirement_code}",
                                    confidence_score=discovered_ctrl.confidence_score,
                                )
                            )

                # Mappings to Threats
                for threat_ref in ctrl_item.threat_ids:
                    target_threat = threat_by_id.get(threat_ref) or threat_by_code.get(threat_ref)
                    if target_threat:
                        existing_map = db.execute(
                            select(ControlThreatMapping).where(
                                ControlThreatMapping.control_id == discovered_ctrl.id,
                                ControlThreatMapping.threat_id == target_threat.id,
                            )
                        ).scalar_one_or_none()
                        if not existing_map:
                            db.add(
                                ControlThreatMapping(
                                    organization_id=run.organization_id,
                                    audit_id=audit.id,
                                    control_id=discovered_ctrl.id,
                                    threat_id=target_threat.id,
                                    mitigation_level="partially_mitigates",
                                    mapping_rationale=f"Control {discovered_ctrl.control_code} mitigates threat scenario {target_threat.threat_id_code}",
                                    confidence_score=discovered_ctrl.confidence_score,
                                )
                            )

            db.flush()

            # 8. Persist Control Assessments
            assessments_saved = 0
            for assess_item in output.assessments:
                target_ctrl = created_controls_map.get(assess_item.control_code)
                if not target_ctrl and created_controls_map:
                    target_ctrl = next(iter(created_controls_map.values()))

                if not target_ctrl:
                    continue

                status = (
                    assess_item.status
                    if assess_item.status in CONTROLLED_ASSESSMENT_STATUSES
                    else "insufficient_evidence"
                )
                maturity = (
                    assess_item.evidence_maturity
                    if assess_item.evidence_maturity in EVIDENCE_MATURITY_LEVELS
                    else target_ctrl.evidence_maturity
                )

                req_target = None
                if assess_item.requirement_id:
                    req_target = req_by_id.get(assess_item.requirement_id) or req_by_code.get(assess_item.requirement_id)

                threat_target = None
                if assess_item.threat_id:
                    threat_target = threat_by_id.get(assess_item.threat_id) or threat_by_code.get(assess_item.threat_id)

                assessment = ControlAssessment(
                    organization_id=run.organization_id,
                    audit_id=audit.id,
                    control_id=target_ctrl.id,
                    defence_analysis_run_id=run.id,
                    requirement_id=req_target.id if req_target else None,
                    threat_id=threat_target.id if threat_target else None,
                    status=status,
                    evidence_maturity=maturity,
                    assessment_explanation=assess_item.assessment_explanation,
                    rationale=assess_item.assessment_explanation,
                    evidence_limitations=assess_item.evidence_limitations,
                    missing_information=assess_item.missing_information,
                    contradictions=assess_item.contradictions,
                    recommended_next_steps=assess_item.recommended_next_steps,
                    confidence_score=assess_item.confidence_score or 0.90,
                    review_status="pending_review",
                )
                db.add(assessment)
                assessments_saved += 1

            # If no explicit assessments returned but controls discovered, create baseline assessments
            if assessments_saved == 0 and created_controls_map:
                for ctrl in created_controls_map.values():
                    assessment = ControlAssessment(
                        organization_id=run.organization_id,
                        audit_id=audit.id,
                        control_id=ctrl.id,
                        defence_analysis_run_id=run.id,
                        requirement_id=approved_reqs[0].id if approved_reqs else None,
                        threat_id=eligible_threats[0].id if eligible_threats else None,
                        status="effective_documented_control" if ctrl.implementation_status == "documented" else "partially_supported_control",
                        evidence_maturity=ctrl.evidence_maturity,
                        assessment_explanation=f"Safeguard {ctrl.name} is documented with {ctrl.evidence_maturity} maturity.",
                        rationale=f"Safeguard {ctrl.name} is documented with {ctrl.evidence_maturity} maturity.",
                        confidence_score=ctrl.confidence_score,
                        review_status="pending_review",
                    )
                    db.add(assessment)
                    assessments_saved += 1

            db.flush()

            # 9. Persist Findings & Gaps
            findings_saved = 0
            gap_counter = 1

            for finding_item in output.findings:
                f_code = finding_item.finding_code or f"GAP-{gap_counter:03d}"
                gap_counter += 1

                category = finding_item.finding_category if finding_item.finding_category in FINDING_CATEGORIES else "documentation_gap"
                risk_score, severity = compute_finding_risk_and_severity(
                    finding_item.likelihood_score,
                    finding_item.impact_score,
                )

                # Distinguish documentation gaps and contradictions from confirmed technical weaknesses
                ev_state = finding_item.evidence_state
                if category in ("documentation_gap", "implementation_evidence_gap", "operational_evidence_gap"):
                    ev_state = "insufficient_evidence"
                elif category == "contradictory_evidence":
                    ev_state = "contradictory_evidence"
                elif ev_state not in ("confirmed_weakness", "insufficient_evidence", "contradictory_evidence"):
                    ev_state = "insufficient_evidence"

                finding = Finding(
                    organization_id=run.organization_id,
                    audit_id=audit.id,
                    defence_analysis_run_id=run.id,
                    finding_code=f_code,
                    title=finding_item.title,
                    description=finding_item.description,
                    severity=severity,
                    evidence_state=ev_state,
                    finding_category=category,
                    likelihood_score=finding_item.likelihood_score,
                    impact_score=finding_item.impact_score,
                    risk_score=risk_score,
                    is_provisional=finding_item.is_provisional,
                    confidence_score=finding_item.confidence_score or 0.88,
                    remediation_guidance=finding_item.remediation_recommendation,
                    remediation_recommendation=finding_item.remediation_recommendation,
                    review_status="pending_review",
                )
                db.add(finding)
                db.flush()

                # Link to related controls
                for c_code in finding_item.related_control_codes:
                    if c_code in created_controls_map:
                        db.add(
                            FindingControl(
                                organization_id=run.organization_id,
                                audit_id=audit.id,
                                finding_id=finding.id,
                                control_id=created_controls_map[c_code].id,
                            )
                        )
                findings_saved += 1

            # 10. Update Run Summary & Metrics
            duration_ms = int((time.time() - start_time) * 1000)
            run.controls_discovered_count = len(created_controls_map)
            run.assessments_count = assessments_saved
            run.findings_count = findings_saved
            run.execution_duration_ms = duration_ms
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.execution_metrics = {
                "duration_ms": duration_ms,
                "input_docs_count": len(audit_docs),
                "input_chunks_count": len(chunks),
                "approved_reqs_count": len(approved_reqs),
                "eligible_threats_count": len(eligible_threats),
                "controls_discovered": len(created_controls_map),
                "assessments_created": assessments_saved,
                "findings_generated": findings_saved,
            }

            db.commit()
            db.refresh(run)
            return run

        except Exception as e:
            logger.exception("Error executing Defence Auditor analysis run %s", run_id)
            db.rollback()
            run = db.execute(select(DefenceAnalysisRun).where(DefenceAnalysisRun.id == run_id)).scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000) if start_time else 0
                run.execution_duration_ms = duration_ms
                db.commit()
                db.refresh(run)
            raise
