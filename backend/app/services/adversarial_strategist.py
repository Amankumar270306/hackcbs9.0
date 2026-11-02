"""Adversarial Strategist service orchestrating threat modeling and attack path analysis."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.assessments import Requirement, Threat
from app.database.models.audits import Audit
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.regulatory import AuditRequirement
from app.database.models.threats import (
    AttackPathNode,
    AttackSurface,
    DiscoveredAsset,
    ThreatAnalysisRun,
    ThreatAsset,
    ThreatEvidenceReference,
    ThreatRequirementMapping,
)
from app.schemas.threats import AdversarialStrategistOutput
from app.services.ai.gemini_client import get_gemini_client
from app.services.ai.prompts.adversarial_strategist import (
    ADVERSARIAL_STRATEGIST_SYSTEM_PROMPT,
    build_threat_analysis_prompt,
)

logger = logging.getLogger(__name__)


def compute_risk_and_severity(likelihood: int, impact: int) -> Tuple[int, str]:
    """Deterministically computes risk score and severity mapping."""
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


class AdversarialStrategistService:
    """Core AI agent engine executing evidence-grounded threat modeling."""

    @staticmethod
    async def run_threat_analysis(db: Session, run_id: UUID) -> ThreatAnalysisRun:
        """Executes full threat modeling pipeline for a ThreatAnalysisRun."""
        run = db.execute(select(ThreatAnalysisRun).where(ThreatAnalysisRun.id == run_id)).scalar_one_or_none()
        if not run:
            raise ValueError(f"ThreatAnalysisRun {run_id} not found.")

        audit = db.execute(select(Audit).where(Audit.id == run.audit_id)).scalar_one_or_none()
        if not audit:
            raise ValueError(f"Audit {run.audit_id} not found.")

        # Update run to running
        start_time = time.time()
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            # 1. Gather audit evidence documents and chunks
            doc_query = select(AuditDocument).where(
                AuditDocument.audit_id == audit.id,
                AuditDocument.organization_id == run.organization_id,
            )
            if run.input_document_ids and len(run.input_document_ids) > 0:
                doc_query = doc_query.where(AuditDocument.id.in_([UUID(did) for did in run.input_document_ids]))

            documents = db.execute(doc_query).scalars().all()
            doc_map = {str(d.id): d for d in documents}

            # Gather chunks for these documents
            doc_ids = [d.id for d in documents]
            chunks: List[DocumentChunk] = []
            if doc_ids:
                chunk_query = select(DocumentChunk).where(
                    DocumentChunk.audit_document_id.in_(doc_ids)
                ).order_by(DocumentChunk.audit_document_id, DocumentChunk.chunk_index)
                chunks = list(db.execute(chunk_query).scalars().all())

            # Format chunks for prompt
            formatted_chunks: List[Dict[str, Any]] = []
            for c in chunks:
                doc = doc_map.get(str(c.audit_document_id))
                formatted_chunks.append({
                    "id": str(c.id),
                    "document_id": str(c.audit_document_id),
                    "filename": (doc.original_filename or doc.file_name) if doc else "document",
                    "page_number": c.page_start or c.page_number or 1,
                    "section_title": c.section_title or "General",
                    "chunk_text": getattr(c, "content", getattr(c, "chunk_text", "")),
                })

            # 2. Gather approved, applicable regulatory requirements
            req_query = (
                select(Requirement)
                .join(AuditRequirement, AuditRequirement.requirement_id == Requirement.id)
                .where(
                    AuditRequirement.audit_id == audit.id,
                    AuditRequirement.applicability_status == "applicable",
                    Requirement.review_status == "approved",
                )
            )
            if run.input_requirement_ids and len(run.input_requirement_ids) > 0:
                req_query = req_query.where(Requirement.id.in_([UUID(rid) for rid in run.input_requirement_ids]))

            approved_reqs = db.execute(req_query).scalars().all()
            req_lookup_by_code: Dict[str, Requirement] = {
                r.requirement_code.strip().upper(): r for r in approved_reqs
            }
            # Also lookup by title or partial code
            for r in approved_reqs:
                req_lookup_by_code[str(r.id)] = r

            formatted_reqs: List[Dict[str, Any]] = [
                {
                    "id": str(r.id),
                    "requirement_code": r.requirement_code,
                    "title": r.title,
                    "category": r.category,
                    "requirement_statement": r.requirement_statement,
                }
                for r in approved_reqs
            ]

            # 3. Assemble Prompt & Call Gemini
            user_prompt = build_threat_analysis_prompt(
                audit_title=audit.title,
                audit_scope=getattr(audit, "description", None) or getattr(audit, "target_system", "Full system boundary"),
                approved_requirements=formatted_reqs,
                document_chunks=formatted_chunks,
            )

            client = get_gemini_client()
            raw_response = await client.generate_structured(
                prompt=user_prompt,
                system_instruction=ADVERSARIAL_STRATEGIST_SYSTEM_PROMPT,
            )

            # 4. Parse & Validate Structured Output
            parsed_output = AdversarialStrategistOutput.model_validate(raw_response)

            # 5. Persist Discovered Assets
            saved_assets: List[DiscoveredAsset] = []
            asset_name_to_obj: Dict[str, DiscoveredAsset] = {}
            for asset_item in parsed_output.assets:
                # Format source references
                serialized_refs = [ref.model_dump(mode="json") for ref in asset_item.source_references]
                asset_obj = DiscoveredAsset(
                    organization_id=run.organization_id,
                    audit_id=audit.id,
                    threat_analysis_run_id=run.id,
                    name=asset_item.name,
                    asset_category=asset_item.asset_category,
                    description=asset_item.description,
                    sensitivity=asset_item.sensitivity,
                    criticality=asset_item.criticality,
                    data_classification=asset_item.data_classification,
                    owner=asset_item.owner or "Unknown",
                    relevant_component=asset_item.relevant_component,
                    evidence_classification=asset_item.evidence_classification,
                    confidence_score=asset_item.confidence_score,
                    source_references=serialized_refs,
                    asset_metadata={"discovered_by": "adversarial_strategist", "run_id": str(run.id)},
                )
                db.add(asset_obj)
                saved_assets.append(asset_obj)
                asset_name_to_obj[asset_item.name.strip().lower()] = asset_obj

            db.flush()  # assign IDs to assets

            # 6. Persist Attack Surfaces
            saved_surfaces: List[AttackSurface] = []
            for surface_item in parsed_output.attack_surfaces:
                serialized_refs = [ref.model_dump(mode="json") for ref in surface_item.source_references]
                surface_obj = AttackSurface(
                    organization_id=run.organization_id,
                    audit_id=audit.id,
                    threat_analysis_run_id=run.id,
                    name=surface_item.name,
                    surface_type=surface_item.surface_type,
                    description=surface_item.description,
                    exposed_component=surface_item.exposed_component,
                    access_requirements=surface_item.access_requirements,
                    trust_boundary=surface_item.trust_boundary,
                    evidence_classification=surface_item.evidence_classification,
                    confidence_score=surface_item.confidence_score,
                    associated_assets=surface_item.associated_assets,
                    source_references=serialized_refs,
                    surface_metadata={"discovered_by": "adversarial_strategist", "run_id": str(run.id)},
                )
                db.add(surface_obj)
                saved_surfaces.append(surface_obj)

            db.flush()

            # 7. Persist Threats, Attack Path Trees, Mappings, and Evidence References
            saved_threats: List[Threat] = []
            for threat_item in parsed_output.threats:
                # Deterministic risk and severity calculation
                risk_score, severity = compute_risk_and_severity(
                    threat_item.likelihood_score,
                    threat_item.impact_score,
                )

                # Flag provisional if critical assumptions or missing info exist
                is_provisional = bool(
                    threat_item.is_provisional
                    or (threat_item.assumptions and len(threat_item.assumptions) > 0)
                    or (threat_item.missing_information and len(threat_item.missing_information) > 0)
                )

                threat_obj = Threat(
                    organization_id=run.organization_id,
                    audit_id=audit.id,
                    threat_analysis_run_id=run.id,
                    threat_title=threat_item.threat_title,
                    threat_description=threat_item.threat_description,
                    stride_category=threat_item.stride_category,
                    threat_category=threat_item.stride_category,
                    attack_objective=threat_item.attack_objective,
                    attack_vector=threat_item.attack_vector,
                    entry_point=threat_item.entry_point,
                    preconditions=threat_item.preconditions,
                    attack_steps=threat_item.attack_steps,
                    target_assets=threat_item.target_assets,
                    affected_components=threat_item.affected_components,
                    trust_boundaries_crossed=threat_item.trust_boundaries_crossed,
                    potential_consequences=threat_item.potential_consequences,
                    cia_confidentiality=threat_item.cia_confidentiality,
                    cia_integrity=threat_item.cia_integrity,
                    cia_availability=threat_item.cia_availability,
                    likelihood_score=threat_item.likelihood_score,
                    likelihood_rationale=threat_item.likelihood_rationale,
                    impact_score=threat_item.impact_score,
                    impact_rationale=threat_item.impact_rationale,
                    risk_score=risk_score,
                    severity=severity,
                    is_provisional=is_provisional,
                    confidence_score=threat_item.confidence_score,
                    review_status="pending_review",
                    assumptions=threat_item.assumptions,
                    missing_information=threat_item.missing_information,
                    threat_metadata={
                        "analysis_summary": parsed_output.analysis_summary,
                        "generated_by": "adversarial_strategist",
                        "run_id": str(run.id),
                    },
                )
                db.add(threat_obj)
                db.flush()  # assign threat_obj.id
                saved_threats.append(threat_obj)

                # Persist Attack Path Nodes
                for seq_idx, node_item in enumerate(threat_item.attack_path, start=1):
                    node_obj = AttackPathNode(
                        organization_id=run.organization_id,
                        audit_id=audit.id,
                        threat_id=threat_obj.id,
                        node_id=node_item.node_id or f"NODE-{seq_idx}",
                        parent_node_id=node_item.parent_node_id,
                        node_type=node_item.node_type,
                        description=node_item.description,
                        logical_operator=node_item.logical_operator,
                        sequence_number=node_item.sequence_number or seq_idx,
                        supporting_references=node_item.supporting_references,
                    )
                    db.add(node_obj)

                # Link discovered assets to threat
                for target_name in threat_item.target_assets:
                    matched_asset = asset_name_to_obj.get(target_name.strip().lower())
                    if matched_asset:
                        threat_asset = ThreatAsset(
                            organization_id=run.organization_id,
                            audit_id=audit.id,
                            threat_id=threat_obj.id,
                            asset_id=matched_asset.id,
                            relationship_type="target_asset",
                        )
                        db.add(threat_asset)

                # Persist Threat Evidence References
                for ref_item in threat_item.source_references:
                    # Resolve document_id and chunk_id
                    matched_doc_id: Optional[UUID] = None
                    matched_chunk_id: Optional[UUID] = None
                    matched_filename: Optional[str] = ref_item.original_filename

                    # Try parsing document_id if valid UUID
                    if ref_item.document_id:
                        try:
                            candidate_uuid = UUID(ref_item.document_id)
                            if str(candidate_uuid) in doc_map:
                                matched_doc_id = candidate_uuid
                        except ValueError:
                            pass

                    # Try matching chunk
                    if ref_item.chunk_id:
                        try:
                            candidate_chunk_uuid = UUID(ref_item.chunk_id)
                            matched_chunk_id = candidate_chunk_uuid
                        except ValueError:
                            pass

                    # Fallback to first document if not matched
                    if not matched_doc_id and documents:
                        matched_doc_id = documents[0].id
                        matched_filename = documents[0].original_filename or documents[0].file_name or "document"

                    # Validate excerpt against chunks text
                    evidence_class = ref_item.evidence_classification
                    if matched_doc_id and ref_item.exact_excerpt:
                        excerpt_lower = ref_item.exact_excerpt.strip().lower()
                        found_verbatim = False
                        for c in chunks:
                            c_text = getattr(c, "content", getattr(c, "chunk_text", ""))
                            if c.audit_document_id == matched_doc_id and excerpt_lower in c_text.lower():
                                found_verbatim = True
                                if not matched_chunk_id:
                                    matched_chunk_id = c.id
                                break
                        if not found_verbatim and evidence_class == "documented_fact":
                            evidence_class = "inference"

                    if matched_doc_id:
                        ev_ref = ThreatEvidenceReference(
                            organization_id=run.organization_id,
                            audit_id=audit.id,
                            threat_id=threat_obj.id,
                            audit_document_id=matched_doc_id,
                            document_chunk_id=matched_chunk_id,
                            original_filename=matched_filename,
                            page_number=ref_item.page_number or (chunk_by_id[str(matched_chunk_id)].page_start if matched_chunk_id and str(matched_chunk_id) in chunk_by_id else None) or 1,
                            section_title=ref_item.section_title,
                            exact_excerpt=ref_item.exact_excerpt,
                            evidence_classification=evidence_class,
                            relevance_explanation=ref_item.relevance_explanation,
                        )
                        db.add(ev_ref)

                # Persist Threat-to-Requirement Mappings (APPROVED ONLY)
                for map_item in threat_item.mapped_requirements:
                    code_key = map_item.requirement_code.strip().upper()
                    matched_req = req_lookup_by_code.get(code_key)
                    if not matched_req:
                        # Try finding by substring of code
                        for k, r in req_lookup_by_code.items():
                            if code_key in k or k in code_key:
                                matched_req = r
                                break

                    if matched_req:
                        # Ensure only approved requirements are mapped
                        if matched_req.review_status == "approved":
                            t_map = ThreatRequirementMapping(
                                organization_id=run.organization_id,
                                audit_id=audit.id,
                                threat_id=threat_obj.id,
                                requirement_id=matched_req.id,
                                relationship_type=map_item.relationship_type,
                                rationale=map_item.rationale,
                                confidence_score=map_item.confidence_score,
                            )
                            db.add(t_map)

            # 8. Complete the run
            elapsed_ms = int((time.time() - start_time) * 1000)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.execution_duration_ms = elapsed_ms
            run.assets_discovered_count = len(saved_assets)
            run.attack_surfaces_count = len(saved_surfaces)
            run.threats_generated_count = len(saved_threats)
            run.execution_metrics = {
                "duration_ms": elapsed_ms,
                "assets_count": len(saved_assets),
                "surfaces_count": len(saved_surfaces),
                "threats_count": len(saved_threats),
                "approved_requirements_evaluated": len(approved_reqs),
                "evidence_chunks_evaluated": len(chunks),
                "analysis_summary": parsed_output.analysis_summary,
            }
            db.commit()
            db.refresh(run)
            return run

        except Exception as e:
            db.rollback()
            logger.exception("Error executing adversarial threat analysis run %s: %s", run_id, str(e))
            # Mark run failed
            run = db.execute(select(ThreatAnalysisRun).where(ThreatAnalysisRun.id == run_id)).scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                if run.started_at:
                    run.execution_duration_ms = int(
                        (run.completed_at - run.started_at).total_seconds() * 1000
                    )
                db.commit()
                db.refresh(run)
            raise
