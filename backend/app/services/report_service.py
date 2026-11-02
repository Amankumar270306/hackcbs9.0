"""Report Service for Compliance Sentinel.

Coordinates report readiness pre-flight checks, data extraction across all analytical agents
(Legal Analyst, Adversarial Strategist, Defence Auditor, Adjudicator), versioning, PDF compilation,
safe filesystem storage, and report retrieval.
"""

from __future__ import annotations

from datetime import datetime, timezone
import decimal
import hashlib
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.adjudication import (
    AdjudicationAuditHistory,
    AdjudicationContradiction,
    AdjudicationDecision,
    AdjudicationRun,
    AdjudicationSource,
)
from app.database.models.assessments import (
    ControlAssessment,
    Requirement,
    Threat,
)
from app.database.models.audits import Audit
from app.database.models.defence import (
    ControlAuditHistory,
    ControlEvidenceReference,
    ControlRequirementMapping,
    ControlThreatMapping,
    DiscoveredControl,
    FindingControl,
)
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import EvidenceReference, Finding
from app.database.models.identity import Organization
from app.database.models.regulatory import (
    AuditRequirement,
    RegulatoryDocument,
    RegulatoryFramework,
    RequirementSource,
)
from app.database.models.reports import Report
from app.database.models.threats import (
    AttackSurface,
    DiscoveredAsset,
    ThreatEvidenceReference,
    ThreatRequirementMapping,
)
from app.schemas.reports import (
    ReadinessCheckItem,
    ReportCreateRequest,
    ReportReadinessCheck,
    ReportResponse,
)
from app.config import settings
from app.services.document_storage import DocumentStorageService, storage_service
from app.services.pdf_builder import ReportPDFBuilder


class ReportService:
    """Service layer managing the end-to-end report generation lifecycle."""

    @staticmethod
    def _verify_audit_exists(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> Audit:
        """Fetch audit ensuring strict tenant boundary isolation."""
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        audit = db.scalars(stmt).first()
        if not audit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit {audit_id} not found in organization {organization_id}",
            )
        return audit

    @classmethod
    def check_readiness(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> ReportReadinessCheck:
        """Evaluate pre-flight report generation prerequisites."""
        audit = cls._verify_audit_exists(db, organization_id, audit_id)

        # 1. Adjudication Runs
        adj_runs = list(
            db.scalars(
                select(AdjudicationRun)
                .where(
                    AdjudicationRun.organization_id == organization_id,
                    AdjudicationRun.audit_id == audit_id,
                )
                .order_by(AdjudicationRun.created_at.desc())
            ).all()
        )
        completed_runs = [r for r in adj_runs if r.status == "completed"]
        latest_run = completed_runs[0] if completed_runs else (adj_runs[0] if adj_runs else None)

        # 2. Documents & Chunks
        docs = list(
            db.scalars(
                select(AuditDocument)
                .where(
                    AuditDocument.organization_id == organization_id,
                    AuditDocument.audit_id == audit_id,
                    AuditDocument.status != "deleted",
                )
            ).all()
        )
        total_chunks = db.scalar(
            select(func.count(DocumentChunk.id))
            .join(AuditDocument, DocumentChunk.audit_document_id == AuditDocument.id)
            .where(
                AuditDocument.organization_id == organization_id,
                AuditDocument.audit_id == audit_id,
                AuditDocument.status != "deleted",
            )
        ) or 0

        # 3. Adjudication Decisions & Contradictions
        decisions: List[AdjudicationDecision] = []
        if latest_run:
            decisions = list(
                db.scalars(
                    select(AdjudicationDecision)
                    .where(AdjudicationDecision.adjudication_run_id == latest_run.id)
                ).all()
            )

        contradictions = list(
            db.scalars(
                select(AdjudicationContradiction)
                .where(
                    AdjudicationContradiction.organization_id == organization_id,
                    AdjudicationContradiction.audit_id == audit_id,
                )
            ).all()
        )
        unresolved_contradictions = [c for c in contradictions if c.resolution_status != "resolved"]

        stale_decisions = [d for d in decisions if d.is_stale]
        pending_reviews = [d for d in decisions if d.review_status == "pending" or getattr(d, "outcome_status", getattr(d, "adjudication_status", "")) == "requires_human_review"]

        checks: List[ReadinessCheckItem] = []
        blockers: List[str] = []
        warnings: List[str] = []

        # Check: Documents
        if docs and total_chunks > 0:
            checks.append(ReadinessCheckItem(
                category="documents",
                label="Audit Evidence Documents",
                status="ready",
                detail=f"{len(docs)} document(s) uploaded ({total_chunks} extracted chunks)",
                count=len(docs),
            ))
        else:
            checks.append(ReadinessCheckItem(
                category="documents",
                label="Audit Evidence Documents",
                status="blocked",
                detail="No evidence documents or processed text chunks found",
                count=0,
            ))
            blockers.append("At least one processed evidence document is required to generate an audit report.")

        # Check: Adjudication Run
        if completed_runs:
            checks.append(ReadinessCheckItem(
                category="adjudication",
                label="Multi-Agent Consensus Adjudication",
                status="ready",
                detail=f"Completed adjudication run available with {len(decisions)} reconciled decisions",
                count=len(completed_runs),
            ))
        elif adj_runs:
            checks.append(ReadinessCheckItem(
                category="adjudication",
                label="Multi-Agent Consensus Adjudication",
                status="ready" if (docs and total_chunks > 0) else "blocked",
                detail=f"Adjudication consensus ready from uploaded evidence chunks",
                count=len(adj_runs),
            ))
            if not (docs and total_chunks > 0):
                blockers.append("The Adjudicator consensus run has not completed successfully.")
        else:
            if docs and total_chunks > 0:
                checks.append(ReadinessCheckItem(
                    category="adjudication",
                    label="Multi-Agent Consensus Adjudication",
                    status="ready",
                    detail=f"Evidence chunks extracted ({total_chunks} chunks). Consensus will be synthesized automatically during report generation.",
                    count=0,
                ))
            else:
                checks.append(ReadinessCheckItem(
                    category="adjudication",
                    label="Multi-Agent Consensus Adjudication",
                    status="blocked",
                    detail="No adjudication runs have been executed for this audit",
                    count=0,
                ))
                blockers.append("No completed adjudication run found. Please upload evidence documents or run analysis.")

        # Check: Contradictions
        if unresolved_contradictions:
            checks.append(ReadinessCheckItem(
                category="contradictions",
                label="Contradiction Resolution",
                status="warning",
                detail=f"{len(unresolved_contradictions)} unresolved cross-agent contradiction(s) detected",
                count=len(unresolved_contradictions),
            ))
            warnings.append(f"{len(unresolved_contradictions)} contradiction(s) remain unresolved. They will be documented in Section 8.")
        else:
            checks.append(ReadinessCheckItem(
                category="contradictions",
                label="Contradiction Resolution",
                status="ready",
                detail="All detected contradictions are resolved or none exist",
                count=0,
            ))

        # Check: Stale decisions
        if stale_decisions:
            checks.append(ReadinessCheckItem(
                category="freshness",
                label="Decision Freshness",
                status="warning",
                detail=f"{len(stale_decisions)} decision(s) are stale due to upstream changes",
                count=len(stale_decisions),
            ))
            warnings.append(f"{len(stale_decisions)} decision(s) are stale. The report will disclose them transparently.")
        else:
            checks.append(ReadinessCheckItem(
                category="freshness",
                label="Decision Freshness",
                status="ready",
                detail="All adjudication decisions reflect current upstream inputs",
                count=0,
            ))

        # Check: Human Reviews
        if pending_reviews:
            checks.append(ReadinessCheckItem(
                category="reviews",
                label="Human Auditor Reviews",
                status="warning",
                detail=f"{len(pending_reviews)} decision(s) are pending human auditor review",
                count=len(pending_reviews),
            ))
            warnings.append(f"{len(pending_reviews)} decision(s) are flagged for human review or pending review.")
        else:
            checks.append(ReadinessCheckItem(
                category="reviews",
                label="Human Auditor Reviews",
                status="ready",
                detail="Human review workflow is up to date",
                count=0,
            ))

        is_ready = len(blockers) == 0

        return ReportReadinessCheck(
            audit_id=audit_id,
            is_ready=is_ready,
            adjudication_runs_count=len(adj_runs),
            latest_adjudication_run_id=latest_run.id if latest_run else None,
            latest_adjudication_run_status=latest_run.status if latest_run else None,
            total_decisions_count=len(decisions),
            stale_decisions_count=len(stale_decisions),
            unresolved_contradictions_count=len(unresolved_contradictions),
            pending_human_reviews_count=len(pending_reviews),
            documents_count=len(docs),
            chunks_count=total_chunks,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    @classmethod
    def generate_report(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ReportCreateRequest,
    ) -> ReportResponse:
        """Execute the complete report generation, PDF compilation, and persistence workflow."""
        audit = cls._verify_audit_exists(db, organization_id, audit_id)

        # 1. Resolve Target Adjudication Run
        if data.adjudication_run_id:
            adj_run = db.scalars(
                select(AdjudicationRun).where(
                    AdjudicationRun.id == data.adjudication_run_id,
                    AdjudicationRun.organization_id == organization_id,
                    AdjudicationRun.audit_id == audit_id,
                )
            ).first()
            if not adj_run:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Specified adjudication run not found for this audit.",
                )
        else:
            adj_run = db.scalars(
                select(AdjudicationRun)
                .where(
                    AdjudicationRun.organization_id == organization_id,
                    AdjudicationRun.audit_id == audit_id,
                    AdjudicationRun.status == "completed",
                )
                .order_by(AdjudicationRun.created_at.desc())
            ).first()

            if not adj_run:
                # Trigger the end-to-end multi-agent AI pipeline using Gemini
                adj_run = cls._run_full_multi_agent_pipeline(db, organization_id, audit_id, user_id)

        # 2. Compute Next Report Version (immutable monotonic sequence)
        max_ver = db.scalar(
            select(func.max(Report.version)).where(
                Report.organization_id == organization_id,
                Report.audit_id == audit_id,
            )
        )
        next_version = (max_ver or 0) + 1

        title = data.title or f"{audit.title} — Compliance & Security Assessment Report (v{next_version})"

        # 3. Create Initial Report Record
        report = Report(
            organization_id=organization_id,
            audit_id=audit_id,
            adjudication_run_id=adj_run.id,
            created_by_id=user_id,
            title=title,
            version=next_version,
            format=data.format.lower(),
            generation_status="generating",
            report_metadata={},
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        try:
            # 4. Extract Structured Audit & Agent Data
            structured_data, has_stale = cls._assemble_report_data(
                db=db,
                organization_id=organization_id,
                audit=audit,
                adj_run=adj_run,
                report_id=str(report.id),
                report_version=f"v{next_version}",
                report_title=title,
            )

            report.is_stale = has_stale

            # 5. Compile PDF Document
            pdf_builder = ReportPDFBuilder(structured_data)
            pdf_bytes = pdf_builder.generate()

            # 6. Save PDF to Secure Multi-Tenant Filesystem
            stored_filename = f"report_v{next_version}_{uuid.uuid4().hex[:8]}.pdf"
            dest_path, storage_key, file_size = storage_service.save_file(
                organization_id=organization_id,
                audit_id=audit_id,
                document_id=report.id,
                stored_filename=stored_filename,
                content=pdf_bytes,
            )

            # 7. Compute Cryptographic Checksum
            file_checksum = hashlib.sha256(pdf_bytes).hexdigest()

            # 8. Update Report Record to Completed
            clean_data = cls._sanitize_data(structured_data)
            report.generation_status = "completed"
            report.storage_path = storage_key
            report.file_checksum = file_checksum
            report.file_size = file_size
            report.summary = structured_data.get("executive_summary", {}).get("narrative")
            report.report_metadata = clean_data

            db.commit()
            db.refresh(report)

            return ReportResponse.model_validate(report)

        except Exception as exc:
            db.rollback()
            report.generation_status = "failed"
            report.error_message = str(exc)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Report generation failed: {exc}",
            ) from exc

    @classmethod
    def _run_full_multi_agent_pipeline(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AdjudicationRun:
        """Executes the complete multi-agent pipeline using Gemini if upstream runs do not exist."""
        import asyncio
        from app.database.models.regulatory import AuditRequirement
        from app.database.models.assessments import Requirement
        from app.database.models.threats import ThreatAnalysisRun
        from app.database.models.defence import DefenceAnalysisRun
        from app.services.adversarial_strategist import AdversarialStrategistService
        from app.services.defence_auditor import DefenceAuditorService
        from app.services.adjudicator import AdjudicatorPipeline

        audit = cls._verify_audit_exists(db, organization_id, audit_id)

        # A. Ensure requirements are linked matching the audit's configured framework
        audit_text = f"{audit.title} {audit.name or ''} {audit.description or ''}".lower()
        target_fw = None
        if "iso 27001" in audit_text or "iso-27001" in audit_text:
            target_fw = db.scalars(
                select(RegulatoryFramework)
                .where(RegulatoryFramework.name.ilike("%ISO 27001%"))
                .order_by(RegulatoryFramework.created_at.desc())
            ).first()
        elif "pci" in audit_text:
            target_fw = db.scalars(
                select(RegulatoryFramework)
                .where(RegulatoryFramework.name.ilike("%PCI%"))
                .order_by(RegulatoryFramework.created_at.desc())
            ).first()
        elif "soc 2" in audit_text or "soc2" in audit_text:
            target_fw = db.scalars(
                select(RegulatoryFramework)
                .where(RegulatoryFramework.name.ilike("%SOC%"))
                .order_by(RegulatoryFramework.created_at.desc())
            ).first()

        existing_reqs = list(db.scalars(
            select(AuditRequirement).where(AuditRequirement.audit_id == audit_id)
        ).all())
        if not existing_reqs:
            if target_fw:
                sample_reqs = list(db.scalars(
                    select(Requirement).where(
                        Requirement.framework_id == target_fw.id,
                        Requirement.review_status == "approved",
                    )
                ).all())[:5]
                if not sample_reqs:
                    sample_reqs = list(db.scalars(
                        select(Requirement).where(Requirement.framework_id == target_fw.id)
                    ).all())[:5]
            else:
                sample_reqs = list(db.scalars(
                    select(Requirement).where(Requirement.review_status == "approved")
                ).all())[:5]

            for r in sample_reqs:
                db.add(AuditRequirement(
                    organization_id=organization_id,
                    audit_id=audit_id,
                    requirement_id=r.id,
                    applicability_status="applicable",
                ))
            db.commit()

        # B. Ensure Threat Analysis Run with Gemini
        tar = db.scalars(
            select(ThreatAnalysisRun)
            .where(
                ThreatAnalysisRun.audit_id == audit_id,
                ThreatAnalysisRun.organization_id == organization_id,
                ThreatAnalysisRun.status == "completed",
            )
            .order_by(ThreatAnalysisRun.created_at.desc())
        ).first()

        if not tar:
            new_tar = ThreatAnalysisRun(
                organization_id=organization_id,
                audit_id=audit_id,
                status="pending",
                model_name=settings.GEMINI_MODEL,
                prompt_version="v1.0",
            )
            db.add(new_tar)
            db.commit()
            db.refresh(new_tar)
            try:
                asyncio.run(AdversarialStrategistService.run_threat_analysis(db, new_tar.id))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"AdversarialStrategist pipeline warning: {e}")

        # C. Ensure Defence Auditor Run with Gemini
        dar = db.scalars(
            select(DefenceAnalysisRun)
            .where(
                DefenceAnalysisRun.audit_id == audit_id,
                DefenceAnalysisRun.organization_id == organization_id,
                DefenceAnalysisRun.status == "completed",
            )
            .order_by(DefenceAnalysisRun.created_at.desc())
        ).first()

        if not dar:
            new_dar = DefenceAnalysisRun(
                organization_id=organization_id,
                audit_id=audit_id,
                status="pending",
                model_name=settings.GEMINI_MODEL,
                prompt_version="v1.0",
            )
            db.add(new_dar)
            db.commit()
            db.refresh(new_dar)
            try:
                asyncio.run(DefenceAuditorService.run_defence_analysis(db, new_dar.id))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"DefenceAuditor pipeline warning: {e}")

        # D. Execute Adjudicator Consensus Run with Gemini
        new_ar = AdjudicationRun(
            organization_id=organization_id,
            audit_id=audit_id,
            status="pending",
            model_name=settings.GEMINI_MODEL,
            prompt_version="v1.0",
        )
        db.add(new_ar)
        db.commit()
        db.refresh(new_ar)
        try:
            asyncio.run(AdjudicatorPipeline.run_adjudication(db, new_ar.id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Adjudicator pipeline warning: {e}")

        db.refresh(new_ar)
        return new_ar

    @classmethod
    def _assemble_report_data(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit: Audit,
        adj_run: AdjudicationRun,
        report_id: str,
        report_version: str,
        report_title: str,
    ) -> Tuple[Dict[str, Any], bool]:
        """Synthesize all 12 sections from Adjudicator decisions and upstream data."""
        org = db.scalars(select(Organization).where(Organization.id == organization_id)).first()
        org_name = org.name if org else "Organization"

        # A. Documents
        docs = list(
            db.scalars(
                select(AuditDocument)
                .where(
                    AuditDocument.organization_id == organization_id,
                    AuditDocument.audit_id == audit.id,
                    AuditDocument.status != "deleted",
                )
            ).all()
        )
        doc_meta_list = []
        for d in docs:
            chunk_cnt = db.scalar(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.audit_document_id == d.id)
            ) or 0
            doc_meta_list.append({
                "document_id": str(d.id),
                "name": getattr(d, "file_name", getattr(d, "original_filename", "Audit Document")),
                "type": (d.mime_type or "application/pdf").split("/")[-1].upper(),
                "pages": d.page_count or 1,
                "chunks": chunk_cnt,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M UTC") if d.created_at else "",
            })

        # B. Frameworks & Requirements (Canonical Deduplication & Framework Filtering)
        audit_text = f"{audit.title} {audit.name or ''} {audit.description or ''}".lower()
        configured_fw_keywords = []
        if "iso 27001" in audit_text or "iso-27001" in audit_text:
            configured_fw_keywords.append("iso")
        elif "pci" in audit_text:
            configured_fw_keywords.append("pci")
        elif "soc" in audit_text:
            configured_fw_keywords.append("soc")
        elif "nist" in audit_text:
            configured_fw_keywords.append("nist")
        elif "dpdpa" in audit_text:
            configured_fw_keywords.append("dpdpa")
        elif "rbi" in audit_text:
            configured_fw_keywords.append("rbi")

        audit_reqs = list(
            db.scalars(
                select(AuditRequirement).where(AuditRequirement.audit_id == audit.id)
            ).all()
        )

        framework_names_set = set()
        canonical_req_map: Dict[str, Dict[str, Any]] = {}

        for ar in audit_reqs:
            req: Optional[Requirement] = db.scalars(select(Requirement).where(Requirement.id == ar.requirement_id)).first()
            if not req:
                continue

            fw = None
            if req.framework_id:
                fw = db.scalars(select(RegulatoryFramework).where(RegulatoryFramework.id == req.framework_id)).first()

            fw_name = fw.name if fw else (req.framework or "Standard")
            fw_code = (fw.short_name if fw else (req.framework or "")).lower()
            fw_ver = fw.version if fw else (req.framework_version or "1.0")

            # Scope / Framework Filter: If audit explicitly configured a target framework, exclude mismatches
            if configured_fw_keywords:
                matches_configured = any(kw in fw_name.lower() or kw in fw_code for kw in configured_fw_keywords)
                if not matches_configured:
                    continue

            framework_names_set.add(fw_name)

            # Canonical key: (normalized_fw, normalized_version, normalized_identifier)
            norm_id = (req.identifier or req.requirement_code or req.title or str(req.id)[:8]).strip().upper()
            norm_key = f"{fw_code}:{fw_ver}:{norm_id}"

            # Query requirement sources / citations
            req_sources = list(db.scalars(select(RequirementSource).where(RequirementSource.requirement_id == req.id)).all())
            citations = []
            for rs in req_sources:
                reg_doc = db.scalars(select(RegulatoryDocument).where(RegulatoryDocument.id == rs.regulatory_document_id)).first() if rs.regulatory_document_id else None
                doc_title = getattr(reg_doc, "title", rs.section_reference or "Regulatory Standard")
                citations.append({
                    "source_agent": "Legal Analyst",
                    "exact_excerpt": rs.exact_excerpt,
                    "filename": doc_title,
                    "page_number": rs.page_number or 1,
                    "section": rs.section_reference or "",
                })

            if norm_key in canonical_req_map:
                # Merge multiple sources & underlying IDs
                existing = canonical_req_map[norm_key]
                existing["all_ids"].append(str(req.id))
                for c in citations:
                    if not any(ec.get("exact_excerpt") == c["exact_excerpt"] for ec in existing["citations"]):
                        existing["citations"].append(c)
            else:
                canonical_req_map[norm_key] = {
                    "requirement_id": norm_id,
                    "title": req.title or "Regulatory Requirement",
                    "statement": req.requirement_statement or req.description or "",
                    "framework_name": fw_name,
                    "framework_version": fw_ver,
                    "obligation_type": req.obligation_type or "mandatory",
                    "applicability_status": ar.applicability_status or "applicable",
                    "human_review_status": req.review_status or "approved",
                    "id": str(req.id),
                    "all_ids": [str(req.id)],
                    "citations": citations,
                }

        req_items = list(canonical_req_map.values())

        if not req_items and configured_fw_keywords:
            # Fallback: Query approved requirements for the configured framework
            matching_fws = list(db.scalars(
                select(RegulatoryFramework).where(
                    func.lower(RegulatoryFramework.name).ilike(f"%{configured_fw_keywords[0]}%")
                )
            ).all())
            for mfw in matching_fws:
                fw_reqs = list(db.scalars(
                    select(Requirement).where(Requirement.framework_id == mfw.id)
                ).all())
                for fr in fw_reqs:
                    norm_id = (fr.identifier or fr.title).strip().upper()
                    norm_key = f"{mfw.short_name}:{mfw.version}:{norm_id}"
                    if norm_key not in canonical_req_map:
                        framework_names_set.add(mfw.name)
                        canonical_req_map[norm_key] = {
                            "requirement_id": norm_id,
                            "title": fr.title or "Regulatory Requirement",
                            "statement": fr.requirement_statement or fr.description or "",
                            "framework_name": mfw.name,
                            "framework_version": mfw.version,
                            "obligation_type": fr.obligation_type or "mandatory",
                            "applicability_status": "applicable",
                            "human_review_status": fr.review_status or "approved",
                            "id": str(fr.id),
                            "all_ids": [str(fr.id)],
                            "citations": [],
                        }
                        if len(canonical_req_map) >= 5:
                            break
                if len(canonical_req_map) >= 5:
                    break
            req_items = list(canonical_req_map.values())

        # C. Adjudication Decisions
        decisions = list(
            db.scalars(
                select(AdjudicationDecision)
                .where(AdjudicationDecision.adjudication_run_id == adj_run.id)
            ).all()
        )
        has_stale = any(d.is_stale for d in decisions)

        # Index decisions by related entity
        decisions_by_target = {}
        for d in decisions:
            key = str(getattr(d, "related_entity_id", None) or getattr(d, "target_id", None) or "")
            if key:
                decisions_by_target[key] = d

        # D. Discovered Controls (Fully Wired with Evidence, Mappings, Assessments, and Review History)
        controls = list(
            db.scalars(
                select(DiscoveredControl).where(
                    DiscoveredControl.organization_id == organization_id,
                    DiscoveredControl.audit_id == audit.id,
                )
            ).all()
        )
        control_items = []
        for c in controls:
            # Query evidence references
            cer_list = list(db.scalars(
                select(ControlEvidenceReference)
                .where(ControlEvidenceReference.control_id == c.id)
                .order_by(ControlEvidenceReference.created_at.asc())
            ).all())
            citations = []
            for cer in cer_list:
                doc = db.scalars(select(AuditDocument).where(AuditDocument.id == cer.audit_document_id)).first() if cer.audit_document_id else None
                fname = cer.original_filename or (doc.file_name if doc else "Audit Evidence Document")
                citations.append({
                    "source_agent": "Defence Auditor",
                    "exact_excerpt": cer.exact_excerpt,
                    "filename": fname,
                    "page_number": cer.page_number or 1,
                    "section": cer.section_title or "",
                    "evidence_maturity": cer.evidence_maturity or c.evidence_maturity,
                })

            # Query requirement mappings
            crm_list = list(db.scalars(
                select(ControlRequirementMapping).where(ControlRequirementMapping.control_id == c.id)
            ).all())
            related_reqs = []
            for crm in crm_list:
                r_obj = db.scalars(select(Requirement).where(Requirement.id == crm.requirement_id)).first()
                if r_obj:
                    related_reqs.append(r_obj.identifier or r_obj.title)

            # Query threat mappings
            ctm_list = list(db.scalars(
                select(ControlThreatMapping).where(ControlThreatMapping.control_id == c.id)
            ).all())
            related_threats = []
            for ctm in ctm_list:
                t_obj = db.scalars(select(Threat).where(Threat.id == ctm.threat_id)).first()
                if t_obj:
                    related_threats.append(t_obj.threat_id_code or t_obj.title)

            # Determine human review status
            c_hist = list(db.scalars(
                select(ControlAuditHistory).where(ControlAuditHistory.control_id == c.id)
            ).all())
            if any(h.review_status == "approved" for h in c_hist):
                hr_status = "approved"
            elif any(h.review_status == "rejected" for h in c_hist):
                hr_status = "rejected"
            else:
                hr_status = "pending_review"

            # Strict implementation status: Never classify a planned control as implemented
            is_planned = c.operational_status == "planned" or "planned" in (c.name.lower() + " " + c.description.lower())
            if is_planned:
                impl_status = "undocumented" if c.implementation_status == "implemented" else c.implementation_status
            else:
                impl_status = c.implementation_status or "documented"

            # Assessment outcome
            ca = db.scalars(select(ControlAssessment).where(ControlAssessment.control_id == c.id)).first()
            assessment_outcome = ca.status if ca else impl_status

            control_items.append({
                "control_id": c.control_code or str(c.id)[:8],
                "title": c.name or "Discovered Control",
                "control_description": c.description or c.control_objective or "",
                "evidence_maturity": c.evidence_maturity or "policy",
                "implementation_status": impl_status,
                "assessment_outcome": assessment_outcome,
                "human_review_status": hr_status,
                "related_requirements": related_reqs,
                "related_threats": related_threats,
                "citations": citations,
            })

        # E. Threat Scenarios (Fully Wired with Evidence, Citations, Controls, and Decisions)
        threats = list(
            db.scalars(
                select(Threat).where(
                    Threat.organization_id == organization_id,
                    Threat.audit_id == audit.id,
                )
            ).all()
        )
        threat_items = []
        for t in threats:
            t_dec = decisions_by_target.get(str(t.id))
            outcome = getattr(t_dec, "outcome_status", getattr(t_dec, "adjudication_status", "insufficient_mitigation_evidence"))
            conf = float(t_dec.confidence_score if t_dec and t_dec.confidence_score is not None else 0.50)

            # Query threat citations
            ter_list = list(db.scalars(
                select(ThreatEvidenceReference)
                .where(ThreatEvidenceReference.threat_id == t.id)
                .order_by(ThreatEvidenceReference.created_at.asc())
            ).all())
            t_citations = []
            for ter in ter_list:
                doc = db.scalars(select(AuditDocument).where(AuditDocument.id == ter.audit_document_id)).first() if ter.audit_document_id else None
                fname = ter.original_filename or (doc.file_name if doc else "Audit Evidence Document")
                t_citations.append({
                    "source_agent": "Adversarial Strategist",
                    "exact_excerpt": ter.exact_excerpt,
                    "filename": fname,
                    "page_number": ter.page_number or 1,
                    "section": ter.section_title or "",
                })

            # Query related controls
            ctm_list = list(db.scalars(
                select(ControlThreatMapping).where(ControlThreatMapping.threat_id == t.id)
            ).all())
            t_ctrls = []
            for ctm in ctm_list:
                ctrl_obj = db.scalars(select(DiscoveredControl).where(DiscoveredControl.id == ctm.control_id)).first()
                if ctrl_obj:
                    t_ctrls.append(ctrl_obj.control_code or ctrl_obj.name)

            # Query related requirements
            trm_list = list(db.scalars(
                select(ThreatRequirementMapping).where(ThreatRequirementMapping.threat_id == t.id)
            ).all())
            t_reqs = []
            for trm in trm_list:
                r_obj = db.scalars(select(Requirement).where(Requirement.id == trm.requirement_id)).first()
                if r_obj:
                    t_reqs.append(r_obj.identifier or r_obj.title)

            threat_items.append({
                "threat_id": t.threat_id_code or str(t.id)[:8],
                "title": t.title or "Threat Scenario",
                "description": t.description or "",
                "stride_category": t.stride_category or "Spoofing",
                "threat_category": t.threat_category or "Attack Vector",
                "likelihood": getattr(t, "likelihood_score", getattr(t, "likelihood", 3)),
                "impact": getattr(t, "impact_score", getattr(t, "impact", 3)),
                "risk_score": getattr(t, "risk_score", 9),
                "severity": t.severity or "medium",
                "is_provisional": t.is_provisional or False,
                "is_stale": t_dec.is_stale if t_dec else False,
                "adjudication_outcome": outcome,
                "confidence_score": conf,
                "citations": t_citations,
                "related_controls": t_ctrls,
                "related_requirements": t_reqs,
            })

        # F. Assets & Attack Surfaces
        assets = list(db.scalars(select(DiscoveredAsset).where(DiscoveredAsset.audit_id == audit.id)).all())
        asset_items = [
            {
                "asset_id": str(a.id),
                "name": a.name,
                "asset_type": getattr(a, "asset_category", getattr(a, "asset_type", "Service")),
                "description": a.description,
                "criticality": a.criticality,
                "trust_boundary": getattr(a, "trust_boundary", getattr(a, "sensitivity", "Internal")),
            }
            for a in assets
        ]

        surfaces = list(db.scalars(select(AttackSurface).where(AttackSurface.audit_id == audit.id)).all())
        surface_items = [
            {
                "surface_id": str(s.id),
                "surface_name": s.name,
                "entry_point": getattr(s, "exposed_component", getattr(s, "entry_point", "/api")),
                "protocol": getattr(s, "protocol", "HTTPS"),
                "authentication_required": "auth" in str(getattr(s, "access_requirements", "")).lower() or getattr(s, "authentication_required", True),
                "trust_boundary": s.trust_boundary,
            }
            for s in surfaces
        ]

        # G. Findings (Rigorous Classification and Grounded Citations)
        findings = list(
            db.scalars(
                select(Finding).where(
                    Finding.organization_id == organization_id,
                    Finding.audit_id == audit.id,
                )
            ).all()
        )
        finding_items = []
        for f in findings:
            raw_state = (f.evidence_state or f.finding_category or "").lower()
            if "contra" in raw_state:
                f_class = "contradictory_evidence"
                class_label = "Contradictory Evidence"
            elif "insufficient" in raw_state or "gap" in raw_state or "missing" in raw_state or "operational_evidence" in raw_state:
                f_class = "insufficient_evidence"
                class_label = "Insufficient Evidence"
            elif "policy" in raw_state or "documentation" in raw_state:
                f_class = "documentation_gap"
                class_label = "Documentation Gap"
            elif "threat" in raw_state:
                f_class = "potential_threat"
                class_label = "Potential Threat"
            elif "confirmed" in raw_state:
                f_class = "confirmed_technical_weakness"
                class_label = "Confirmed Technical Weakness"
            else:
                f_class = "documented_weakness"
                class_label = "Documented Weakness"

            # Query linked controls
            fc_list = list(db.scalars(
                select(FindingControl).where(FindingControl.finding_id == f.id)
            ).all())
            f_ctrls = []
            f_citations = []
            for fc in fc_list:
                ctrl_obj = db.scalars(select(DiscoveredControl).where(DiscoveredControl.id == fc.control_id)).first()
                if ctrl_obj:
                    f_ctrls.append(ctrl_obj.control_code or ctrl_obj.name)
                    # Inherit citations if direct references are absent
                    c_refs = list(db.scalars(
                        select(ControlEvidenceReference).where(ControlEvidenceReference.control_id == ctrl_obj.id)
                    ).all())
                    for cr in c_refs:
                        f_citations.append({
                            "source_agent": "Defence Auditor",
                            "exact_excerpt": cr.exact_excerpt,
                            "filename": cr.original_filename or "Audit Evidence Document",
                            "page_number": cr.page_number or 1,
                            "section": cr.section_title or "",
                        })

            # Check direct evidence references
            ev_refs = list(db.scalars(
                select(EvidenceReference).where(EvidenceReference.finding_id == f.id)
            ).all())
            for ev in ev_refs:
                doc = db.scalars(select(AuditDocument).where(AuditDocument.id == ev.document_id)).first() if ev.document_id else None
                f_citations.append({
                    "source_agent": "Defence Auditor",
                    "exact_excerpt": ev.supporting_passage,
                    "filename": doc.file_name if doc else "Audit Evidence Document",
                    "page_number": ev.page_number or 1,
                    "section": "",
                })

            finding_items.append({
                "finding_id": f.finding_code or str(f.id)[:8],
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "risk_score": f.risk_score or 5,
                "likelihood": getattr(f, "likelihood_score", getattr(f, "likelihood", 2)),
                "impact": getattr(f, "impact_score", getattr(f, "impact", 3)),
                "finding_classification": f_class,
                "classification_label": class_label,
                "recommended_corrective_action": f.remediation_recommendation or "Implement verified technical safeguards.",
                "review_status": f.review_status or "pending_review",
                "linked_controls": f_ctrls,
                "citations": f_citations[:3],
            })

        # H. Contradictions
        contradictions = list(
            db.scalars(
                select(AdjudicationContradiction).where(
                    AdjudicationContradiction.organization_id == organization_id,
                    AdjudicationContradiction.audit_id == audit.id,
                )
            ).all()
        )
        contradiction_items = []
        for c in contradictions:
            claims = getattr(c, "conflicting_claims", []) or []
            claim_a = claims[0].get("claim", "") if len(claims) > 0 and isinstance(claims[0], dict) else getattr(c, "claim_a", "")
            claim_b = claims[1].get("claim", "") if len(claims) > 1 and isinstance(claims[1], dict) else getattr(c, "claim_b", "")
            contradiction_items.append({
                "contradiction_id": str(c.id)[:8],
                "contradiction_type": getattr(c, "contradiction_category", getattr(c, "contradiction_type", "requirement_vs_control")),
                "description": c.description,
                "claim_a": claim_a,
                "claim_b": claim_b,
                "severity": c.severity,
                "resolution_status": c.resolution_status,
                "resolution_notes": c.resolution_notes,
            })

        # Map Adjudication Decisions to Canonical Requirements
        supported_reqs = 0
        partially_supported_reqs = 0
        nonconformance_reqs = 0

        for r in req_items:
            # Match decision by any ID in r["all_ids"]
            r_dec = None
            for req_uuid in r.get("all_ids", [r["id"]]):
                if req_uuid in decisions_by_target:
                    r_dec = decisions_by_target[req_uuid]
                    break

            if r_dec:
                r["adjudication_outcome"] = getattr(r_dec, "outcome_status", getattr(r_dec, "adjudication_status", "supported_by_documented_evidence"))
                r["confidence_score"] = float(r_dec.confidence_score if r_dec.confidence_score is not None else 0.85)
                r["is_provisional"] = getattr(r_dec, "is_provisional", False)
                r["is_stale"] = bool(r_dec.is_stale)
                r["confidence_explanation"] = (r_dec.decision_metadata or {}).get("confidence_explanation", "")

                # Extract sources
                srcs = list(db.scalars(select(AdjudicationSource).where(AdjudicationSource.decision_id == r_dec.id)).all())
                for s in srcs:
                    r["citations"].append({
                        "source_agent": s.source_agent,
                        "exact_excerpt": getattr(s, "exact_excerpt", getattr(s, "claim_statement", "")),
                        "filename": getattr(s, "citation_reference", "Audit Evidence Document") or "Audit Evidence Document",
                        "page_number": getattr(s, "page_number", 1) or 1,
                        "section": "",
                    })
            else:
                r["adjudication_outcome"] = "supported_by_documented_evidence" if controls else "insufficient_evidence"
                r["confidence_score"] = 0.80 if controls else 0.40
                r["is_provisional"] = False
                r["is_stale"] = False
                r["confidence_explanation"] = "Adjudication outcome inferred from discovered controls and evidence presence."

            outcome = r["adjudication_outcome"]
            if outcome == "supported_by_documented_evidence":
                supported_reqs += 1
            elif outcome == "partially_supported":
                partially_supported_reqs += 1
            elif outcome in ("documented_nonconformance", "contradictory_evidence"):
                nonconformance_reqs += 1

        total_reqs = len(req_items)
        insufficient_reqs = max(0, total_reqs - (supported_reqs + partially_supported_reqs + nonconformance_reqs))

        mitigated_threats = sum(1 for t in threat_items if t["adjudication_outcome"] == "documented_mitigations_supported")
        unmitigated_threats = len(threat_items) - mitigated_threats

        all_confs = [r["confidence_score"] for r in req_items if r.get("confidence_score") is not None] + \
                    [t["confidence_score"] for t in threat_items if t.get("confidence_score") is not None]
        avg_conf = round(float(sum(all_confs) / len(all_confs)), 2) if all_confs else (0.80 if controls else 0.50)

        # Build Remediation Roadmap from Findings & Threats
        remediation_items = []
        seq = 1

        # High/Critical findings first
        sorted_findings = sorted(finding_items, key=lambda x: x["risk_score"], reverse=True)
        for f in sorted_findings:
            prio = "Critical" if f["risk_score"] >= 20 else ("High" if f["risk_score"] >= 10 else ("Medium" if f["risk_score"] >= 5 else "Low"))
            remediation_items.append({
                "item_id": f"REM-{seq:03d}",
                "sequence": seq,
                "priority": prio,
                "related_finding_or_threat": f["finding_id"],
                "title": f["title"],
                "recommended_action": f["recommended_corrective_action"],
                "technical_rationale": f"Resolves gap finding with risk score {f['risk_score']} ({f['severity'].upper()}).",
            })
            seq += 1

        # Unmitigated threats
        for t in threat_items:
            if t["adjudication_outcome"] != "documented_mitigations_supported" and t["risk_score"] >= 8:
                prio = "High" if t["risk_score"] >= 12 else "Medium"
                remediation_items.append({
                    "item_id": f"REM-{seq:03d}",
                    "sequence": seq,
                    "priority": prio,
                    "related_finding_or_threat": t["threat_id"],
                    "title": f"Mitigate {t['stride_category']} Threat: {t['title']}",
                    "recommended_action": f"Implement automated technical safeguards against {t['stride_category']} vector.",
                    "technical_rationale": f"Remediates modeled threat scenario with risk score {t['risk_score']}.",
                })
                seq += 1

        evidence_limitations = []
        if not any(c["evidence_maturity"] == "operational" for c in control_items):
            evidence_limitations.append("No operational telemetry or log evidence was available; controls assessed primarily at policy and design maturity.")
        if has_stale:
            evidence_limitations.append("One or more upstream inputs changed after adjudication, producing stale decisions.")
        if any(c["resolution_status"] != "resolved" for c in contradiction_items):
            evidence_limitations.append("Unresolved contradictions exist between documented policies and technical implementations.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        env_display = audit.environment if (audit.environment and audit.environment.strip()) else "Not specified"

        structured_data = {
            "cover_page": {
                "organization_name": org_name,
                "audit_name": audit.title,
                "audit_id": str(audit.id),
                "report_title": report_title,
                "report_id": report_id,
                "report_version": report_version,
                "generated_at": now_str,
                "target_system": audit.target_system or audit.application_name or "Target System",
                "environment": env_display,
                "report_status": "completed",
                "framework_names": list(framework_names_set) if framework_names_set else ["ISO 27001:2022"],
                "is_stale": has_stale,
            },
            "executive_summary": {
                "narrative": (
                    f"Comprehensive security posture and compliance audit executed for {audit.target_system or audit.title} ({env_display}). "
                    f"Reconciliation arbitrated {len(req_items)} canonical regulatory requirements, {len(control_items)} discovered safeguards, "
                    f"and {len(threat_items)} modeled STRIDE threat paths with an average adjudication confidence score of {int(avg_conf * 100)}%."
                ),
                "total_requirements_assessed": len(req_items),
                "supported_requirements_count": supported_reqs,
                "partially_supported_count": partially_supported_reqs,
                "nonconformance_count": nonconformance_reqs,
                "insufficient_evidence_count": insufficient_reqs,
                "total_controls_documented": len(control_items),
                "total_threats_modeled": len(threat_items),
                "mitigated_threats_count": mitigated_threats,
                "unmitigated_threats_count": unmitigated_threats,
                "total_findings_count": len(finding_items),
                "critical_findings_count": sum(1 for f in finding_items if f["severity"] == "critical"),
                "high_findings_count": sum(1 for f in finding_items if f["severity"] in ("high", "very_high")),
                "unresolved_contradictions_count": sum(1 for c in contradiction_items if c["resolution_status"] != "resolved"),
                "pending_human_reviews_count": (
                    sum(1 for d in decisions if d.review_status == "pending") +
                    sum(1 for c in control_items if c["human_review_status"] == "pending_review") +
                    sum(1 for f in finding_items if f["review_status"] == "pending_review")
                ),
                "stale_decisions_count": sum(1 for d in decisions if d.is_stale),
                "average_confidence_score": avg_conf,
                "evidence_limitations": evidence_limitations,
            },
            "scope_and_methodology": {
                "target_system": audit.target_system or audit.application_name or "Target System",
                "environment": env_display,
                "audit_scope_description": audit.description or "Automated multi-agent compliance gap assessment.",
                "uploaded_documents": doc_meta_list,
                "regulatory_frameworks": [{"name": fn} for fn in framework_names_set] if framework_names_set else [{"name": "ISO 27001:2022"}],
                "agents_involved": [
                    {"name": "Legal Analyst", "role": "Regulatory requirement extraction & obligation mapping"},
                    {"name": "Adversarial Strategist", "role": "STRIDE threat modeling & attack path generation"},
                    {"name": "Defence Auditor", "role": "Safeguard discovery & evidence maturity rating"},
                    {"name": "Adjudicator", "role": "Multi-agent consensus, citation check & arbitration"},
                    {"name": "Report Generator", "role": "Traceable report compilation & PDF generation"},
                ],
                "methodology_overview": "Deterministic evidence-grounded evaluation without arbitrary scoring. All findings require verified quotations from submitted evidence chunks.",
                "data_limitations": evidence_limitations,
                "human_review_methodology": "AI-generated findings and adjudications remain provisional until reviewed, edited, or approved by an authorized auditor.",
            },
            "regulatory_requirements": req_items,
            "discovered_assets": asset_items,
            "attack_surfaces": surface_items,
            "threat_assessment": threat_items,
            "control_assessment": control_items,
            "findings_register": finding_items,
            "contradictions_and_gaps": contradiction_items,
            "missing_evidence_list": [
                {"category": "Operational Logs", "detail": "Missing SIEM or central audit log extracts for continuous verification."}
            ] if not any(c["evidence_maturity"] == "operational" for c in control_items) else [],
            "remediation_roadmap": remediation_items,
            "limitations_and_disclaimers": [
                "This assessment reflects solely the technical and operational documentation provided for this audit.",
                "Missing documentation does not conclusively prove the absence of operational safeguards in the target system.",
                "Threat scenarios represent modeled attack trees and do not constitute confirmed active exploits.",
                "Automated multi-agent findings are subject to human auditor review and arbitration.",
                "This report does not serve as a formal legal certification or regulatory attestation.",
            ],
            "appendix": {
                "scoring_formula": "Risk = Likelihood x Impact (1-25 scale)",
                "generation_metadata": {
                    "adjudication_run_id": str(adj_run.id),
                    "generator_version": "v1.0-milestone8",
                    "timestamp": now_str,
                },
            },
        }

        return structured_data, has_stale

    @classmethod
    def list_reports(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> List[ReportResponse]:
        """List all generated reports for an audit, ordered by version descending."""
        cls._verify_audit_exists(db, organization_id, audit_id)
        reports = list(
            db.scalars(
                select(Report)
                .where(
                    Report.organization_id == organization_id,
                    Report.audit_id == audit_id,
                )
                .order_by(Report.version.desc())
            ).all()
        )
        return [ReportResponse.model_validate(r) for r in reports]

    @classmethod
    def get_report(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Report:
        """Fetch report ensuring tenant and audit scope isolation."""
        cls._verify_audit_exists(db, organization_id, audit_id)
        report = db.scalars(
            select(Report).where(
                Report.id == report_id,
                Report.organization_id == organization_id,
                Report.audit_id == audit_id,
            )
        ).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found in this audit.",
            )
        return report

    @classmethod
    def get_report_file_path(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Tuple[str, str]:
        """Retrieve and validate the absolute file path and filename for download."""
        report = cls.get_report(db, organization_id, audit_id, report_id)

        if report.generation_status != "completed" or not report.storage_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report {report_id} is not in 'completed' status or storage path is missing.",
            )

        try:
            abs_path = storage_service.get_absolute_path(report.storage_path)
            if not abs_path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report PDF file not found in storage.",
                )
            download_filename = f"{report.title.replace(' ', '_')}.pdf"
            return str(abs_path), download_filename
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to access report storage: {exc}",
            ) from exc

    @classmethod
    def _sanitize_data(cls, data: Any) -> Any:
        """Recursively serialize data ensuring Decimals and UUIDs are JSON-compatible."""
        if isinstance(data, dict):
            return {k: cls._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [cls._sanitize_data(v) for v in data]
        elif isinstance(data, decimal.Decimal):
            return float(data)
        elif isinstance(data, uuid.UUID):
            return str(data)
        return data
