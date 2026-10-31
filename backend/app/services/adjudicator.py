"""Adjudicator service orchestrating cross-agent reconciliation, consensus, and contradiction detection (Milestone 7)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.adjudication import (
    AdjudicationContradiction,
    AdjudicationDecision,
    AdjudicationRun,
    AdjudicationSource,
)
from app.database.models.assessments import ControlAssessment, Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.defence import (
    ControlEvidenceReference,
    ControlRequirementMapping,
    ControlThreatMapping,
    DiscoveredControl,
)
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import Finding
from app.database.models.regulatory import AuditRequirement
from app.schemas.adjudication import AdjudicatorOutput
from app.services.ai.gemini_client import get_gemini_client
from app.services.ai.prompts.adjudicator import (
    ADJUDICATOR_ANALYSIS_PROMPT,
    ADJUDICATOR_SYSTEM_INSTRUCTION,
)

logger = logging.getLogger(__name__)


def compute_deterministic_confidence(
    evidence_maturity: Optional[str] = "policy",
    outcome_status: Optional[str] = "supported_by_documented_evidence",
    has_invalid_citations: bool = False,
    has_contradictions: bool = False,
    is_pending_threat: bool = False,
    missing_agent_data: bool = False,
    is_human_reviewed: bool = False,
) -> float:
    """Calculates deterministic confidence score for an adjudication decision based on strict evidentiary constraints."""
    # Base score derived from evidence maturity
    maturity = (evidence_maturity or "policy").lower()
    if maturity == "operational":
        base_score = 0.90
    elif maturity == "implementation":
        base_score = 0.80
    elif maturity == "design":
        base_score = 0.65
    elif maturity == "policy":
        base_score = 0.50
    else:
        base_score = 0.40

    # Adjust for outcome status
    outcome = (outcome_status or "").lower()
    if outcome in ("insufficient_evidence", "insufficient_mitigation_evidence"):
        base_score = min(base_score, 0.40)
    elif outcome in ("contradictory_evidence", "requires_human_review"):
        base_score = min(base_score, 0.45)

    # Penalties
    if has_invalid_citations:
        base_score -= 0.25
    if has_contradictions:
        base_score -= 0.20
    if missing_agent_data:
        base_score = min(base_score - 0.15, 0.60)
    if is_pending_threat:
        base_score = min(base_score, 0.70)

    # Bonus for human-approved source
    if is_human_reviewed:
        base_score += 0.05

    # Clamp between 0.10 and 0.98
    return round(max(0.10, min(0.98, float(base_score))), 2)


class AdjudicatorPipeline:
    """Core AI consensus engine executing cross-agent reconciliation."""

    @staticmethod
    async def run_adjudication(db: Session, run_id: UUID) -> AdjudicationRun:
        """Executes full adjudication pipeline for an AdjudicationRun."""
        run = db.execute(select(AdjudicationRun).where(AdjudicationRun.id == run_id)).scalar_one_or_none()
        if not run:
            raise ValueError(f"AdjudicationRun {run_id} not found.")

        audit = db.execute(select(Audit).where(Audit.id == run.audit_id)).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {run.audit_id} not found.")

        start_time = time.time()
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            # 1. Collect and filter inputs according to source eligibility rules
            # A. Documents & Chunks
            doc_query = select(AuditDocument).where(
                AuditDocument.audit_id == audit.id,
                AuditDocument.organization_id == run.organization_id,
            )
            audit_docs = list(db.execute(doc_query).scalars().all())
            doc_ids = [d.id for d in audit_docs]

            chunks: List[DocumentChunk] = []
            chunk_lookup: Dict[str, DocumentChunk] = {}
            if doc_ids:
                chunks_query = (
                    select(DocumentChunk)
                    .where(DocumentChunk.audit_document_id.in_(doc_ids))
                    .order_by(DocumentChunk.audit_document_id, DocumentChunk.chunk_index)
                )
                chunks = list(db.execute(chunks_query).scalars().all())
                for ch in chunks:
                    chunk_lookup[str(ch.id)] = ch

            # B. Requirements (Legal Analyst)
            req_query = (
                select(Requirement, AuditRequirement)
                .join(AuditRequirement, AuditRequirement.requirement_id == Requirement.id)
                .where(
                    AuditRequirement.audit_id == audit.id,
                    AuditRequirement.organization_id == run.organization_id,
                )
            )
            req_rows = list(db.execute(req_query).all())
            # Separate approved requirements from pending, exclude rejected
            approved_reqs: List[Tuple[Requirement, AuditRequirement]] = []
            pending_reqs: List[Tuple[Requirement, AuditRequirement]] = []
            for r, ar in req_rows:
                status = (r.review_status or "pending_review").lower()
                if status == "approved":
                    approved_reqs.append((r, ar))
                elif status in ("pending", "pending_review", "under_review"):
                    pending_reqs.append((r, ar))
                # rejected requirements are explicitly excluded from primary conclusions

            # Use approved requirements primarily; if none approved, use pending as provisional
            eligible_reqs = approved_reqs if approved_reqs else pending_reqs
            req_is_provisional = len(approved_reqs) == 0

            # C. Threats (Adversarial Strategist)
            threat_query = select(Threat).where(
                Threat.audit_id == audit.id,
                Threat.organization_id == run.organization_id,
            )
            all_threats = list(db.execute(threat_query).scalars().all())
            accepted_threats = [t for t in all_threats if (t.review_status or "").lower() == "accepted"]
            pending_threats = [t for t in all_threats if (t.review_status or "").lower() in ("pending", "needs_review", "")]
            # Rejected threats are explicitly excluded from conclusions
            eligible_threats = accepted_threats + pending_threats

            # D. Controls, Assessments & Findings (Defence Auditor)
            ctrl_query = select(DiscoveredControl).where(
                DiscoveredControl.audit_id == audit.id,
                DiscoveredControl.organization_id == run.organization_id,
            )
            all_controls = list(db.execute(ctrl_query).scalars().all())

            assess_query = select(ControlAssessment).where(
                ControlAssessment.audit_id == audit.id,
                ControlAssessment.organization_id == run.organization_id,
            )
            all_assessments = list(db.execute(assess_query).scalars().all())

            finding_query = select(Finding).where(
                Finding.audit_id == audit.id,
                Finding.organization_id == run.organization_id,
            )
            all_findings = list(db.execute(finding_query).scalars().all())

            # Map control assessment review statuses
            ctrl_review_status: Dict[UUID, str] = {}
            for a in all_assessments:
                if a.control_id and a.review_status:
                    ctrl_review_status[a.control_id] = a.review_status

            # Check missing agents
            missing_agents: List[str] = []
            if not eligible_reqs:
                missing_agents.append("Legal Analyst (No approved or pending regulatory requirements)")
            if not eligible_threats:
                missing_agents.append("Adversarial Strategist (No accepted or pending threat scenarios)")
            if not all_controls:
                missing_agents.append("Defence Auditor (No discovered security controls)")

            # Record snapshot of inputs
            run.input_source_snapshot = {
                "requirements_count": len(eligible_reqs),
                "approved_requirements_count": len(approved_reqs),
                "threats_count": len(eligible_threats),
                "accepted_threats_count": len(accepted_threats),
                "controls_count": len(all_controls),
                "assessments_count": len(all_assessments),
                "findings_count": len(all_findings),
                "chunks_count": len(chunks),
                "missing_agents": missing_agents,
            }

            # 2. Build structured input payload for Gemini Adjudicator
            input_context = {
                "audit": {
                    "id": str(audit.id),
                    "target_name": audit.target_system or "System",
                    "application_name": audit.application_name or "Audit Workload",
                },
                "applicable_regulatory_requirements": [
                    {
                        "requirement_id": str(r.id),
                        "requirement_code": r.requirement_code,
                        "title": r.title,
                        "statement": r.requirement_statement or r.description,
                        "obligation_type": r.obligation_type,
                        "review_status": r.review_status,
                    }
                    for r, ar in eligible_reqs
                ],
                "threat_scenarios": [
                    {
                        "threat_id": str(t.id),
                        "title": t.title,
                        "stride_category": t.stride_category,
                        "risk_score": float(t.risk_score) if t.risk_score else 0.0,
                        "review_status": t.review_status,
                    }
                    for t in eligible_threats
                ],
                "discovered_controls": [
                    {
                        "control_id": str(c.id),
                        "control_code": c.control_code,
                        "name": c.name,
                        "category": c.category,
                        "implementation_status": c.implementation_status,
                        "evidence_maturity": c.evidence_maturity,
                        "review_status": ctrl_review_status.get(c.id, "pending_review"),
                    }
                    for c in all_controls
                ],
                "evidence_document_chunks": [
                    {
                        "chunk_id": str(ch.id),
                        "document_id": str(ch.audit_document_id),
                        "page_number": ch.page_number,
                        "section_title": ch.section_title or "General",
                        "content": ch.content[:400],
                    }
                    for ch in chunks[:20]
                ],
            }

            prompt_text = ADJUDICATOR_ANALYSIS_PROMPT.format(
                audit_context_json=json.dumps(input_context, indent=2)
            )

            # 3. Invoke LLM for structured reasoning
            client = get_gemini_client()
            raw_response = await client.generate_structured(
                prompt=prompt_text,
                system_instruction=ADJUDICATOR_SYSTEM_INSTRUCTION,
            )

            # Validate output with Pydantic
            validated_output = AdjudicatorOutput.model_validate(raw_response)

            # 4. Deterministic Contradiction Detection across agents
            detected_contradictions: List[Dict[str, Any]] = []

            # Check Requirement vs Control contradictions (e.g. Mandatory technical requirement, but only policy evidence exists)
            for r, ar in eligible_reqs:
                r_id_str = str(r.id)
                mapped_ctrls = [c for c in all_controls if c.category and c.category.lower() in (r.category or "").lower()]
                for c in mapped_ctrls:
                    if (c.evidence_maturity or "").lower() == "policy" and (r.obligation_type or "").lower() == "mandatory":
                        detected_contradictions.append({
                            "category": "requirement_vs_control",
                            "title": f"Policy-Only Safeguard for Mandatory Obligation {r.requirement_code}",
                            "description": f"Requirement {r.requirement_code} mandates technical safeguards, but control {c.control_code} only provides policy-level documentation without operational proof.",
                            "conflicting_claims": [
                                {
                                    "claim": f"Mandatory obligation {r.requirement_code}: {(r.requirement_statement or r.description or '')[:120]}",
                                    "source_agent": "legal_analyst",
                                    "source_entity_id": r_id_str,
                                },
                                {
                                    "claim": f"Control {c.control_code} ({c.name}) evidence maturity is policy only.",
                                    "source_agent": "defence_auditor",
                                    "source_entity_id": str(c.id),
                                },
                            ],
                            "source_references": [
                                {"source_agent": "legal_analyst", "entity_id": r_id_str},
                                {"source_agent": "defence_auditor", "entity_id": str(c.id)},
                            ],
                            "impact": "Requirement cannot be considered fully operational; human verification required.",
                            "severity": "medium",
                        })

            # Check Threat vs Control contradictions (High severity threat on surface vs unverified or design-only control)
            for t in eligible_threats:
                t_score = float(t.risk_score or 0)
                if t_score >= 12.0:  # High / Critical threat
                    for c in all_controls:
                        if (c.evidence_maturity or "").lower() in ("policy", "design"):
                            detected_contradictions.append({
                                "category": "threat_vs_control",
                                "title": f"High Risk Threat {t.title[:40]} Lacks Operational Safeguards",
                                "description": f"Threat scenario has high risk score ({t_score}), but safeguard {c.control_code} is only at {c.evidence_maturity} maturity.",
                                "conflicting_claims": [
                                    {
                                        "claim": f"High risk threat scenario: {t.title}",
                                        "source_agent": "adversarial_strategist",
                                        "source_entity_id": str(t.id),
                                    },
                                    {
                                        "claim": f"Safeguard {c.control_code} is documented only at {c.evidence_maturity} maturity.",
                                        "source_agent": "defence_auditor",
                                        "source_entity_id": str(c.id),
                                    },
                                ],
                                "source_references": [
                                    {"source_agent": "adversarial_strategist", "entity_id": str(t.id)},
                                    {"source_agent": "defence_auditor", "entity_id": str(c.id)},
                                ],
                                "impact": "High risk remains insufficiently addressed until operational telemetry is attached.",
                                "severity": "high",
                            })
                            break  # record one per high-risk threat

            # Check AI vs Human Review contradictions
            for c in all_controls:
                c_review = (ctrl_review_status.get(c.id, "")).lower()
                if c_review in ("rejected", "more_info_requested"):
                    detected_contradictions.append({
                        "category": "ai_vs_human_review",
                        "title": f"Human Review Rejection of AI Discovered Control {c.control_code}",
                        "description": f"Control {c.control_code} was identified by AI Defence Auditor, but rejected by human reviewer ({c_review}). Human decision takes strict precedence.",
                        "conflicting_claims": [
                            {
                                "claim": f"AI identified control {c.control_code} as documented safeguard.",
                                "source_agent": "defence_auditor",
                                "source_entity_id": str(c.id),
                            },
                            {
                                "claim": f"Human reviewer marked control assessment as {c_review}.",
                                "source_agent": "human_reviewer",
                                "source_entity_id": str(c.id),
                            },
                        ],
                        "source_references": [
                            {"source_agent": "defence_auditor", "entity_id": str(c.id)},
                            {"source_agent": "human_reviewer", "entity_id": str(c.id)},
                        ],
                        "impact": "Control is disqualified from satisfying compliance obligations.",
                        "severity": "high",
                    })

            # Also incorporate any contradictions generated by LLM
            for contra in validated_output.contradictions:
                detected_contradictions.append({
                    "category": contra.category,
                    "title": contra.title,
                    "description": contra.description,
                    "conflicting_claims": contra.conflicting_claims,
                    "source_references": contra.source_references,
                    "impact": contra.impact,
                    "severity": contra.severity,
                })

            # Persist AdjudicationContradictions
            created_contradictions: List[AdjudicationContradiction] = []
            for item in detected_contradictions:
                contra_model = AdjudicationContradiction(
                    organization_id=run.organization_id,
                    audit_id=run.audit_id,
                    adjudication_run_id=run.id,
                    contradiction_category=item["category"],
                    title=item["title"][:255],
                    description=item["description"],
                    conflicting_claims=item.get("conflicting_claims", []),
                    source_references=item.get("source_references", []),
                    impact=item["impact"],
                    severity=item.get("severity", "medium"),
                    resolution_status="unresolved",
                )
                db.add(contra_model)
                created_contradictions.append(contra_model)

            db.flush()

            # 5. Process Decisions and verify citations against real chunks
            created_decisions: List[AdjudicationDecision] = []

            for dec_item in validated_output.decisions:
                # Resolve related entity
                related_id: Optional[UUID] = None
                if dec_item.related_entity_id:
                    try:
                        related_id = UUID(dec_item.related_entity_id)
                    except Exception:
                        pass

                # If requirement decision and requirement was not approved, mark provisional
                is_prov = dec_item.is_provisional
                if dec_item.related_entity_type == "requirement" and req_is_provisional:
                    is_prov = True
                elif dec_item.related_entity_type == "threat":
                    # Check if threat is pending
                    matched_threat = next((t for t in eligible_threats if str(t.id) == str(related_id)), None)
                    if matched_threat and (matched_threat.review_status or "").lower() != "accepted":
                        is_prov = True

                has_contra = len(detected_contradictions) > 0
                req_review = dec_item.requires_human_review or has_contra

                # Determine evidence maturity for confidence calculation
                ev_maturity = "policy"
                if all_controls:
                    ev_maturity = all_controls[0].evidence_maturity or "policy"

                # Citation verification pass
                has_invalid_cite = False
                source_models: List[AdjudicationSource] = []

                for s_item in dec_item.supporting_sources:
                    is_valid = True
                    notes: Optional[str] = None
                    chunk_obj: Optional[DocumentChunk] = None

                    if s_item.chunk_id and s_item.chunk_id in chunk_lookup:
                        chunk_obj = chunk_lookup[s_item.chunk_id]
                        # Verify excerpt against chunk content
                        if s_item.exact_excerpt and s_item.exact_excerpt.strip():
                            sub = s_item.exact_excerpt.strip().lower()[:60]
                            if sub not in chunk_obj.content.lower():
                                is_valid = False
                                has_invalid_cite = True
                                notes = "Excerpt not found verbatim in cited document chunk."
                    elif s_item.chunk_id:
                        is_valid = False
                        has_invalid_cite = True
                        notes = f"Referenced chunk {s_item.chunk_id} not found in audit documents."

                    # Resolve source entity id
                    s_ent_id = uuid.uuid4()
                    if s_item.source_entity_id:
                        try:
                            s_ent_id = UUID(s_item.source_entity_id)
                        except Exception:
                            pass
                    elif related_id:
                        s_ent_id = related_id

                    source_m = AdjudicationSource(
                        organization_id=run.organization_id,
                        audit_id=run.audit_id,
                        source_agent=s_item.source_agent if s_item.source_agent in (
                            "legal_analyst", "adversarial_strategist", "defence_auditor", "document_extractor", "human_reviewer"
                        ) else "defence_auditor",
                        source_entity_type=s_item.source_entity_type if s_item.source_entity_type in (
                            "regulatory_requirement", "threat_scenario", "discovered_control", "control_assessment", "finding", "document_chunk"
                        ) else "discovered_control",
                        source_entity_id=s_ent_id,
                        source_role=s_item.source_role if s_item.source_role in ("supporting", "contradictory", "contextual", "informational") else "supporting",
                        citation_reference=s_item.filename or (chunk_obj.audit_document.filename if chunk_obj and chunk_obj.audit_document else "document"),
                        exact_excerpt=s_item.exact_excerpt,
                        chunk_id=chunk_obj.id if chunk_obj else None,
                        document_id=chunk_obj.audit_document_id if chunk_obj else None,
                        page_number=chunk_obj.page_number if chunk_obj else s_item.page_number,
                        section_heading=chunk_obj.section_title if chunk_obj else s_item.section_heading,
                        is_citation_valid=is_valid,
                        citation_validation_notes=notes,
                    )
                    source_models.append(source_m)

                # Deterministic confidence computation
                conf = compute_deterministic_confidence(
                    evidence_maturity=ev_maturity,
                    outcome_status=dec_item.outcome_status,
                    has_invalid_citations=has_invalid_cite,
                    has_contradictions=has_contra,
                    is_pending_threat=is_prov,
                    missing_agent_data=len(missing_agents) > 0,
                    is_human_reviewed=False,
                )

                decision_m = AdjudicationDecision(
                    organization_id=run.organization_id,
                    audit_id=run.audit_id,
                    adjudication_run_id=run.id,
                    decision_category=dec_item.category if dec_item.category in (
                        "requirement_compliance", "threat_mitigation", "control_effectiveness", "cross_cutting"
                    ) else "requirement_compliance",
                    related_entity_type=dec_item.related_entity_type if dec_item.related_entity_type in (
                        "requirement", "threat", "control", "general"
                    ) else "general",
                    related_entity_id=related_id,
                    outcome_status=dec_item.outcome_status,
                    summary=dec_item.summary,
                    reasoning=dec_item.reasoning,
                    confidence_score=conf,
                    is_provisional=is_prov,
                    requires_human_review=req_review or has_invalid_cite,
                    is_stale=False,
                    evidence_limitations=dec_item.evidence_limitations,
                    assumptions=dec_item.assumptions,
                    missing_information=dec_item.missing_information,
                    recommended_action=dec_item.recommended_action,
                    review_status="pending_review",
                    decision_metadata={
                        "missing_agents": missing_agents,
                        "invalid_citations_detected": has_invalid_cite,
                    },
                )
                db.add(decision_m)
                db.flush()

                # Link sources to decision
                for sm in source_models:
                    sm.decision_id = decision_m.id
                    db.add(sm)

                created_decisions.append(decision_m)

            # Update run completion counters
            run.status = "completed"
            run.requirements_processed_count = len(eligible_reqs)
            run.threats_processed_count = len(eligible_threats)
            run.controls_processed_count = len(all_controls)
            run.decisions_generated_count = len(created_decisions)
            run.contradictions_detected_count = len(created_contradictions)
            run.completed_at = datetime.now(timezone.utc)
            run.execution_duration_ms = int((time.time() - start_time) * 1000)
            run.execution_metrics = {
                "duration_seconds": round(time.time() - start_time, 2),
                "decisions_count": len(created_decisions),
                "contradictions_count": len(created_contradictions),
                "missing_agents": missing_agents,
            }

            db.commit()
            db.refresh(run)
            return run

        except Exception as exc:
            logger.exception("Error executing Adjudicator consensus run: %s", exc)
            db.rollback()
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            run.execution_duration_ms = int((time.time() - start_time) * 1000)
            db.commit()
            raise

