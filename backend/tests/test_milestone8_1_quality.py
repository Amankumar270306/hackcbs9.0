"""Comprehensive regression test suite for Milestone 8.1: Report Quality and Pipeline Accuracy.

Validates the 13 essential quality and precision requirements:
1. Canonical requirement deduplication merges duplicate identifiers/obligations.
2. Multiple citations are preserved across merged requirements.
3. Generic control placeholders ("Documented Control: Pages 1-") are prohibited.
4. Planned controls are never classified as implemented.
5. Missing evidence is classified as insufficient_evidence or documentation_gap.
6. Contradictions are properly classified and penalized without duplicate stacking.
7. Framework selection consistency matches audit configuration.
8. Target environment metadata consistency (no silent production default).
9. Confidence score calculation avoids compound duplicate penalties and includes explanation.
10. Long text in PDF tables and paragraphs wraps without truncation.
11. Unicode characters render without "?" replacement marks.
12. PDF regeneration increments version and preserves cryptographic SHA-256 integrity.
13. Multi-tenant isolation for report access and download.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.adjudication import (
    AdjudicationContradiction,
    AdjudicationDecision,
    AdjudicationRun,
    AdjudicationSource,
)
from app.database.models.assessments import ControlAssessment, Requirement, Threat
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
from app.database.models.identity import Organization, User
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
from app.main import app
from app.services.adjudicator import AdjudicatorPipeline
from app.services.pdf_builder import ReportPDFBuilder, sanitize_pdf_text
from app.services.report_service import ReportService
from app.schemas.reports import ReportCreateRequest


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_user_and_audit(client: TestClient, org_name: str, audit_name: str, description: str = "", environment: str = "production") -> dict:
    """Helper to set up authenticated organization, user, and audit."""
    uid = uuid.uuid4().hex[:8]
    email = f"quality_auditor_{uid}@sentinel.org"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"Auditor {uid}",
            "email": email,
            "password": "Password123!",
            "organization_name": org_name,
        },
    )
    assert res.status_code == 201
    auth_data = res.json()
    headers = {"Authorization": f"Bearer {auth_data['access_token']}"}

    audit_res = client.post(
        f"/api/organizations/{auth_data['organization_id']}/audits",
        headers=headers,
        json={
            "name": audit_name,
            "application_name": "ShopSphere VPC",
            "target_system": "E-Commerce Microservices",
            "description": description,
        },
    )
    assert audit_res.status_code == 201
    audit_data = audit_res.json()

    # If environment is non-default, update directly in DB
    db = SessionLocal()
    audit_obj = db.scalars(select(Audit).where(Audit.id == uuid.UUID(audit_data["id"]))).first()
    if audit_obj:
        audit_obj.environment = environment
        db.commit()
    db.close()

    return {
        "user_id": uuid.UUID(auth_data["user_id"]),
        "org_id": uuid.UUID(auth_data["organization_id"]),
        "audit_id": uuid.UUID(audit_data["id"]),
        "headers": headers,
    }


# ===========================================================================
# 1. Canonical Requirement Deduplication & Preservation of Citations
# ===========================================================================

def test_canonical_requirement_deduplication_and_citation_preservation():
    """Requirement 1 & 2: Merge duplicate requirements and preserve all citations."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        # Create framework
        fw = RegulatoryFramework(
            name="PCI-DSS Standard v4.0",
            short_name="PCI-DSS",
            issuing_authority="PCI SSC",
            version="4.0",
            status="active",
        )
        db.add(fw)
        db.flush()

        # Create two separate requirement records representing the same canonical obligation
        req1 = Requirement(
            framework="PCI-DSS",
            framework_id=fw.id,
            framework_version="4.0",
            identifier="PCI-REQ-8.3",
            title="Multi-Factor Authentication",
            description="MFA must be implemented for all administrative access.",
            requirement_statement="Implement MFA for administrative and remote CDE access.",
            review_status="approved",
        )
        req2 = Requirement(
            framework="PCI-DSS",
            framework_id=fw.id,
            framework_version="4.0",
            identifier="PCI-REQ-8.3",
            title="Multi-Factor Authentication",
            description="MFA must be implemented for all administrative access.",
            requirement_statement="Implement MFA for administrative and remote CDE access.",
            review_status="approved",
        )
        db.add_all([req1, req2])
        db.flush()

        # Create regulatory document and sources
        reg_doc = RegulatoryDocument(
            framework_id=fw.id,
            title="PCI DSS v4.0 Official Standard",
            document_type="standard",
            status="processed",
        )
        db.add(reg_doc)
        db.flush()

        src1 = RequirementSource(
            requirement_id=req1.id,
            regulatory_document_id=reg_doc.id,
            section_reference="Section 8.3.1",
            page_number=54,
            exact_excerpt="Multi-factor authentication (MFA) is implemented for all administrative access to the CDE.",
        )
        src2 = RequirementSource(
            requirement_id=req2.id,
            regulatory_document_id=reg_doc.id,
            section_reference="Section 8.3.2",
            page_number=55,
            exact_excerpt="MFA is required for all remote network access originating from outside the entity's network.",
        )
        db.add_all([src1, src2])

        # Link both to audit
        ar1 = AuditRequirement(organization_id=org_id, audit_id=audit_id, requirement_id=req1.id, applicability_status="applicable")
        ar2 = AuditRequirement(organization_id=org_id, audit_id=audit_id, requirement_id=req2.id, applicability_status="applicable")
        db.add_all([ar1, ar2])

        audit = Audit(
            id=audit_id,
            organization_id=org_id,
            title="Payment Gateway PCI Audit",
            target_system="Payment Service",
            description="PCI-DSS compliance audit",
            environment="production",
        )
        db.add(audit)
        db.flush()

        # Test deduplication during report data assembly
        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        structured_data, _ = ReportService._assemble_report_data(
            db=db,
            organization_id=org_id,
            audit=audit,
            adj_run=adj_run,
            report_id=str(uuid.uuid4()),
            report_version="v1",
            report_title="Test Report",
        )

        reqs = structured_data["regulatory_requirements"]
        # Exactly 1 canonical requirement should exist (not 2 duplicates)
        assert len(reqs) == 1
        canonical_req = reqs[0]
        assert canonical_req["requirement_id"] == "PCI-REQ-8.3"

        # Citations from BOTH underlying records must be preserved
        cites = canonical_req["citations"]
        assert len(cites) == 2
        excerpts = [c["exact_excerpt"] for c in cites]
        assert "Section 8.3.1" in str(cites) or any("Section 8.3.1" in c.get("section", "") for c in cites) or any("8.3" in e for e in excerpts)

        # Executive summary must count canonical requirements (1), not raw extractions (2)
        ex = structured_data["executive_summary"]
        assert ex["total_requirements_assessed"] == 1

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 2. Control Discovery: Generic Placeholders Prohibited & Planned Controls
# ===========================================================================

def test_generic_control_placeholders_prohibited_and_planned_not_implemented():
    """Requirement 3 & 4: No generic placeholders and planned controls never marked implemented."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        audit = Audit(
            id=audit_id,
            organization_id=org_id,
            title="ShopSphere Architecture Audit",
            target_system="ShopSphere E-Commerce",
            environment="production",
        )
        db.add(audit)

        # Control A: Documented Control with Real Name
        ctrl_a = DiscoveredControl(
            organization_id=org_id,
            audit_id=audit_id,
            control_code="CTRL-001",
            name="Password Hashing with Argon2id",
            description="User passwords are salted and hashed using Argon2id with 64MB memory cost.",
            category="Identity & Access Management",
            control_objective="Prevent credential exposure in database compromise scenarios.",
            implementation_status="documented",
            operational_status="active",
            evidence_maturity="design",
        )

        # Control B: Planned Control
        ctrl_b = DiscoveredControl(
            organization_id=org_id,
            audit_id=audit_id,
            control_code="CTRL-002",
            name="Planned Multi-Factor Authentication",
            description="Planned implementation of FIDO2 WebAuthn authentication in Q2 roadmap.",
            category="Authentication",
            control_objective="Mandate multi-factor authentication for administrators.",
            implementation_status="implemented",  # Upstream falsely marked implemented
            operational_status="planned",
            evidence_maturity="policy",
        )
        db.add_all([ctrl_a, ctrl_b])
        db.flush()

        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        structured_data, _ = ReportService._assemble_report_data(
            db=db,
            organization_id=org_id,
            audit=audit,
            adj_run=adj_run,
            report_id=str(uuid.uuid4()),
            report_version="v1",
            report_title="Test Report",
        )

        controls = structured_data["control_assessment"]
        assert len(controls) == 2

        # 1. Prohibit generic placeholders
        for c in controls:
            assert "Pages 1-" not in c["title"]
            assert "Pages 3-" not in c["title"]
            assert not c["title"].startswith("Documented Control: Pages")

        # 2. Planned control must be demoted from 'implemented'
        planned_ctrl = next(c for c in controls if c["control_id"] == "CTRL-002")
        assert planned_ctrl["implementation_status"] != "implemented"
        assert planned_ctrl["implementation_status"] in ("undocumented", "planned")

        # 3. Discovered controls are NOT automatically marked approved
        for c in controls:
            assert c["human_review_status"] == "pending_review"

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 3. Finding Classification & Missing Evidence Handling
# ===========================================================================

def test_finding_classification_and_missing_evidence():
    """Requirement 5: Rigorous finding classification and missing evidence."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        audit = Audit(id=audit_id, organization_id=org_id, title="Audit", target_system="System")
        db.add(audit)

        f1 = Finding(
            organization_id=org_id,
            audit_id=audit_id,
            finding_code="FIND-01",
            title="Database Backup Policy Missing Operational Verification",
            description="Policy states backups occur daily, but no automated restore runbooks exist.",
            severity="medium",
            evidence_state="operational_evidence_gap",
            finding_category="documentation_gap",
            risk_score=6,
        )
        f2 = Finding(
            organization_id=org_id,
            audit_id=audit_id,
            finding_code="FIND-02",
            title="Contradictory Log Retention Period Statements",
            description="Section 4 states 90 days retention, while Section 9 states 30 days.",
            severity="low",
            evidence_state="contradictory_evidence",
            finding_category="contradiction",
            risk_score=3,
        )
        db.add_all([f1, f2])
        db.flush()

        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        data, _ = ReportService._assemble_report_data(
            db=db, organization_id=org_id, audit=audit, adj_run=adj_run,
            report_id=str(uuid.uuid4()), report_version="v1", report_title="Test",
        )

        findings = data["findings_register"]
        assert len(findings) == 2

        f1_item = next(f for f in findings if f["finding_id"] == "FIND-01")
        assert f1_item["classification_label"] in ("Insufficient Evidence", "Documentation Gap")

        f2_item = next(f for f in findings if f["finding_id"] == "FIND-02")
        assert f2_item["classification_label"] == "Contradictory Evidence"

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 4. Framework and Scope Consistency
# ===========================================================================

def test_framework_selection_consistency_matches_audit_configuration():
    """Requirement 7: Audit only uses exact framework configured; excludes mismatched frameworks."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        # Audit explicitly configured for ISO 27001
        audit = Audit(
            id=audit_id,
            organization_id=org_id,
            title="ShopSphere E-Commerce Platform",
            description="Compliance assessment under ISO 27001:2022 framework",
            target_system="shopsphere-production-vpc",
            environment="production",
        )
        db.add(audit)
        db.flush()

        fw_iso = RegulatoryFramework(name="ISO 27001:2022", short_name="ISO-27001", issuing_authority="ISO", version="2022")
        fw_pci = RegulatoryFramework(name="PCI-DSS Standard v4.0", short_name="PCI-DSS", issuing_authority="PCI SSC", version="4.0")
        db.add_all([fw_iso, fw_pci])
        db.flush()

        r_iso = Requirement(framework="ISO-27001", framework_id=fw_iso.id, identifier="A.9.4.2", title="Secure Log-on Procedures", description="Desc")
        r_pci = Requirement(framework="PCI-DSS", framework_id=fw_pci.id, identifier="PCI-REQ-8.3", title="MFA Access", description="Desc")
        db.add_all([r_iso, r_pci])
        db.flush()

        # Inadvertently or previously linked both to audit
        db.add(AuditRequirement(organization_id=org_id, audit_id=audit_id, requirement_id=r_iso.id, applicability_status="applicable"))
        db.add(AuditRequirement(organization_id=org_id, audit_id=audit_id, requirement_id=r_pci.id, applicability_status="applicable"))
        db.flush()

        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        data, _ = ReportService._assemble_report_data(
            db=db, organization_id=org_id, audit=audit, adj_run=adj_run,
            report_id=str(uuid.uuid4()), report_version="v1", report_title="Test",
        )

        reqs = data["regulatory_requirements"]
        # Only the ISO 27001 requirement must be present; PCI-DSS must be excluded
        req_ids = [r["requirement_id"] for r in reqs]
        assert "A.9.4.2" in req_ids
        assert "PCI-REQ-8.3" not in req_ids

        # Frameworks in cover page must reflect ISO 27001
        assert any("ISO" in fn for fn in data["cover_page"]["framework_names"])

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 5. Target Environment Metadata Consistency
# ===========================================================================

def test_target_environment_metadata_consistency():
    """Requirement 8: Environment does not silently default to production if unspecified."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        # Audit with empty environment
        audit = Audit(
            id=audit_id,
            organization_id=org_id,
            title="Staging Test Audit",
            target_system="Staging API",
            environment="",
        )
        db.add(audit)
        db.flush()

        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        data, _ = ReportService._assemble_report_data(
            db=db, organization_id=org_id, audit=audit, adj_run=adj_run,
            report_id=str(uuid.uuid4()), report_version="v1", report_title="Test",
        )

        env = data["cover_page"]["environment"]
        assert env == "Not specified"
        assert env != "production"

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 6. Confidence Score Calculation & Explanations
# ===========================================================================

def test_confidence_score_calculation_avoids_compound_duplicate_penalties():
    """Requirement 6 & 9: Confidence score avoids duplicate compounding penalties."""
    # Direct test of the adjudicator compute_deterministic_confidence logic
    class DummyTarget:
        id = uuid.uuid4()

    # Case 1: Discovered control without operational telemetry (policy/design)
    controls = [{"name": "Auth", "operational_status": "active", "evidence_maturity": "design", "citations": ["doc.pdf"]}]
    threats = [{"severity": "medium", "citations": ["doc.pdf"]}]
    findings = [{"category": "documentation_gap", "severity": "low"}]
    citations = [{"page_number": 1, "exact_excerpt": "Valid excerpt"}]
    contradictions = []

    conf, explanation = AdjudicatorPipeline.compute_deterministic_confidence(
        target_entity=DummyTarget(),
        discovered_controls=controls,
        evaluated_threats=threats,
        findings=findings,
        matched_citations=citations,
        contradictions=contradictions,
        agent_consensus_count=3,
    )

    # Confidence must reflect grounded design evidence (~0.60-0.75), not artificially collapsed to 0.11
    assert conf >= 0.50
    assert "explanation" in explanation.lower() or "base confidence" in explanation.lower()

    # Case 2: Contradiction present
    contradictions = [{"description": "Policy contradicts deployment note", "severity": "high"}]
    conf_contra, expl_contra = AdjudicatorPipeline.compute_deterministic_confidence(
        target_entity=DummyTarget(),
        discovered_controls=controls,
        evaluated_threats=threats,
        findings=findings,
        matched_citations=citations,
        contradictions=contradictions,
        agent_consensus_count=3,
    )
    # Contradiction should apply a controlled penalty (-0.15) once, not duplicate penalty
    diff = round(conf - conf_contra, 2)
    assert diff == 0.15
    assert "contradiction" in expl_contra.lower()


# ===========================================================================
# 7. Executive Summary Mathematical Consistency
# ===========================================================================

def test_executive_summary_internal_mathematical_consistency():
    """Requirement 8: Strict mathematical consistency in executive summary counts."""
    db = SessionLocal()
    try:
        org_id = uuid.uuid4()
        audit_id = uuid.uuid4()

        audit = Audit(id=audit_id, organization_id=org_id, title="Audit", target_system="Sys")
        db.add(audit)

        # 3 requirements
        for idx in range(3):
            req = Requirement(framework="ISO", identifier=f"A.{idx+1}", title=f"Req {idx+1}", description="D")
            db.add(req)
            db.flush()
            db.add(AuditRequirement(organization_id=org_id, audit_id=audit_id, requirement_id=req.id))

        # 2 threats
        for idx in range(2):
            thr = Threat(organization_id=org_id, audit_id=audit_id, threat_id_code=f"THR-{idx+1}", title=f"Thr {idx+1}", description="D", risk_score=8)
            db.add(thr)

        adj_run = AdjudicationRun(organization_id=org_id, audit_id=audit_id, status="completed")
        db.add(adj_run)
        db.flush()

        data, _ = ReportService._assemble_report_data(
            db=db, organization_id=org_id, audit=audit, adj_run=adj_run,
            report_id=str(uuid.uuid4()), report_version="v1", report_title="Test",
        )

        ex = data["executive_summary"]
        total_reqs = ex["total_requirements_assessed"]
        sup = ex["supported_requirements_count"]
        part = ex["partially_supported_count"]
        nonconf = ex["nonconformance_count"]
        insuff = ex["insufficient_evidence_count"]

        # Equation 1: Sum of requirement partitions must equal total
        assert sup + part + nonconf + insuff == total_reqs

        # Equation 2: Mitigated + Unmitigated must equal total threats
        total_threats = ex["total_threats_modeled"]
        mit = ex["mitigated_threats_count"]
        unmit = ex["unmitigated_threats_count"]
        assert mit + unmit == total_threats

    finally:
        db.rollback()
        db.close()


# ===========================================================================
# 8. Unicode Sanitization & PDF Rendering
# ===========================================================================

def test_unicode_characters_render_without_question_marks():
    """Requirement 11: Typographic characters render without '?' replacement marks."""
    sample_text = (
        'Testing typography: em-dash \u2014 here, en-dash \u2013 here, '
        'bullet \u2022 here, smart quotes \u201cquote\u201d and \u2018single\u2019, '
        'and arrows \u2192.'
    )
    clean = sanitize_pdf_text(sample_text)
    assert "?" not in clean
    assert "--" in clean
    assert '"quote"' in clean
    assert "'single'" in clean


def test_long_text_wrapping_in_pdf_without_truncation():
    """Requirement 10: Multi-page and long paragraph text wraps cleanly."""
    long_desc = "Security safeguard description " * 40  # ~1200 characters
    data = {
        "cover_page": {"audit_name": "Wrap Test", "report_title": "Wrap Report", "report_id": "R1", "report_version": "v1", "generated_at": "Now"},
        "executive_summary": {"narrative": long_desc, "total_requirements_assessed": 1, "average_confidence_score": 0.8},
        "scope_and_methodology": {"target_system": "Target", "uploaded_documents": []},
        "regulatory_requirements": [{"requirement_id": "REQ-01", "title": "Requirement", "statement": long_desc, "adjudication_outcome": "supported_by_documented_evidence", "citations": []}],
        "discovered_assets": [],
        "attack_surfaces": [],
        "threat_assessment": [],
        "control_assessment": [{"control_id": "CTRL-01", "title": "Control 1", "control_description": long_desc, "implementation_status": "documented", "evidence_maturity": "design", "citations": []}],
        "findings_register": [{"finding_id": "GAP-01", "title": "Gap 1", "description": long_desc, "severity": "high", "risk_score": 12, "recommended_corrective_action": long_desc}],
        "contradictions_and_gaps": [],
        "missing_evidence_list": [],
        "remediation_roadmap": [],
        "limitations_and_disclaimers": ["Disclaimer text"],
        "appendix": {"generation_metadata": {}},
    }

    builder = ReportPDFBuilder(data)
    pdf_bytes = builder.generate()
    assert len(pdf_bytes) > 5000

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    # Verify that PDF was created and text is readable
    all_text = " ".join(page.get_text() for page in doc)
    assert "Security safeguard description" in all_text
    assert "?" not in all_text


# ===========================================================================
# 9. PDF Regeneration, Versioning, SHA-256 Integrity, & Multi-Tenant Isolation
# ===========================================================================

def test_pdf_regeneration_versioning_and_multi_tenant_isolation(client: TestClient):
    """Requirement 12 & 13: Version increment, SHA-256 integrity, and multi-tenant security."""
    # Org A
    org_a = create_user_and_audit(client, "Company A", "Company A Audit")
    db = SessionLocal()

    # Org B (Attacker / Different Tenant)
    org_b = create_user_and_audit(client, "Company B", "Company B Audit")

    # Generate Report v1 for Org A
    req = ReportCreateRequest(title="Org A Audit Report v1", format="pdf")
    rep1 = ReportService.generate_report(db, org_a["org_id"], org_a["audit_id"], org_a["user_id"], req)
    assert rep1.version == 1
    assert rep1.file_checksum is not None
    assert len(rep1.file_checksum) == 64

    # Generate Report v2 for Org A
    rep2 = ReportService.generate_report(db, org_a["org_id"], org_a["audit_id"], org_a["user_id"], req)
    assert rep2.version == 2
    assert rep2.file_checksum is not None
    assert rep2.id != rep1.id

    # Verify Multi-Tenant Isolation: Org B user cannot download or view Org A report
    res_b = client.get(
        f"/api/organizations/{org_b['org_id']}/audits/{org_a['audit_id']}/reports/{rep1.id}",
        headers=org_b["headers"],
    )
    # Must fail with 404 or 403
    assert res_b.status_code in (403, 404)

    # Direct report download by unauthorized user must be forbidden
    res_download = client.get(
        f"/api/organizations/{org_b['org_id']}/audits/{org_a['audit_id']}/reports/{rep1.id}/download",
        headers=org_b["headers"],
    )
    assert res_download.status_code in (403, 404)

    # Authorized download by Org A must succeed
    res_auth = client.get(
        f"/api/organizations/{org_a['org_id']}/audits/{org_a['audit_id']}/reports/{rep1.id}/download",
        headers=org_a["headers"],
    )
    assert res_auth.status_code == 200
    assert res_auth.headers["content-type"] == "application/pdf"
    # Verify cryptographic hash of returned binary matches stored checksum
    downloaded_hash = hashlib.sha256(res_auth.content).hexdigest()
    assert downloaded_hash == rep1.file_checksum

    db.close()

