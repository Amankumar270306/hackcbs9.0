"""Comprehensive test suite for Milestone 8: Report Generator & PDF Compilation.

Validates:
1. Report readiness pre-flight check (enforcing completed adjudication runs and documents).
2. Full report generation pipeline synthesizing all 12 sections from Adjudicator outputs.
3. PDF generation, cryptographic SHA-256 checksumming, file size, and file existence.
4. Report versioning and immutability (v1, v2, ... monotonic increment).
5. Stale decision disclosure in report metadata and executive summary.
6. Report preview JSON and direct binary PDF download endpoints.
7. Multi-tenant and RBAC security isolation.
"""

from __future__ import annotations

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
from app.database.models.defence import DiscoveredControl
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.findings import Finding
from app.database.models.regulatory import AuditRequirement, RegulatoryFramework
from app.database.models.reports import Report
from app.database.models.threats import AttackSurface, DiscoveredAsset
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_auth_user(client: TestClient, org_name: str = "Report Test Org") -> dict:
    """Helper to register user and obtain auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"reporter_{uid}@sentinel-test.com"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"Report Officer {uid}",
            "email": email,
            "password": "Password123!",
            "organization_name": org_name,
        },
    )
    assert res.status_code == 201
    data = res.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": data["user_id"],
        "email": email,
        "org_id": data["organization_id"],
    }


def create_sample_audit(client: TestClient, user: dict) -> str:
    """Helper to create an audit."""
    res = client.post(
        f"/api/organizations/{user['org_id']}/audits",
        headers=user["headers"],
        json={
            "name": "PCI-DSS Compliance Assessment Audit",
            "application_name": "Payment Gateway API",
            "target_system": "AWS EKS & YugabyteDB",
            "description": "Comprehensive security and compliance audit for production payment processing.",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def populate_audit_data_with_adjudication(audit_id: str, org_id: str) -> dict:
    """Insert comprehensive multi-agent records into database for report synthesis."""
    db = SessionLocal()
    try:
        a_uuid = uuid.UUID(audit_id)
        o_uuid = uuid.UUID(org_id)

        # 1. Evidence Document & Chunks
        doc = AuditDocument(
            organization_id=o_uuid,
            audit_id=a_uuid,
            file_name="Payment_System_Architecture_v2.pdf",
            original_filename="Payment_System_Architecture_v2.pdf",
            stored_filename="Payment_System_Architecture_v2.pdf",
            mime_type="application/pdf",
            file_size_bytes=45000,
            status="completed",
            page_count=12,
            chunk_count=1,
            extracted_text_length=14500,
            storage_path=f"{org_id}/{audit_id}/docs/arch.pdf",
            checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        db.add(doc)
        db.flush()

        chunk = DocumentChunk(
            organization_id=o_uuid,
            audit_id=a_uuid,
            audit_document_id=doc.id,
            chunk_index=0,
            content="All sensitive cardholder data is protected at rest using AES-256-GCM. Administrative access enforces hardware MFA tokens.",
            page_number=3,
            section_title="Cryptography & Authentication",
            character_count=120,
            start_char_offset=0,
            end_char_offset=120,
        )
        db.add(chunk)
        db.flush()

        # 2. Regulatory Framework & Requirement
        fw = RegulatoryFramework(
            name="PCI-DSS v4.0",
            short_name=f"PCI-DSS-{uuid.uuid4().hex[:6]}",
            issuing_authority="PCI Security Standards Council",
            version="4.0",
            status="active",
        )
        db.add(fw)
        db.flush()

        req = Requirement(
            framework_id=fw.id,
            identifier="PCI-REQ-8.3",
            title="Multi-Factor Authentication",
            description="Enforce MFA for all administrative access into the cardholder data environment.",
            requirement_statement="All access to CDE requires multi-factor authentication.",
            obligation_type="mandatory",
            review_status="approved",
        )
        db.add(req)
        db.flush()

        audit_req = AuditRequirement(
            organization_id=o_uuid,
            audit_id=a_uuid,
            requirement_id=req.id,
            applicability_status="applicable",
        )
        db.add(audit_req)

        # 3. Discovered Asset & Attack Surface
        asset = DiscoveredAsset(
            organization_id=o_uuid,
            audit_id=a_uuid,
            name="Cardholder Database Cluster",
            asset_category="Database",
            description="Production database cluster storing primary account numbers.",
            criticality="critical",
            sensitivity="confidential",
        )
        db.add(asset)

        surface = AttackSurface(
            organization_id=o_uuid,
            audit_id=a_uuid,
            name="Payment REST API",
            surface_type="api_endpoint",
            description="Production payment REST ingress endpoint.",
            exposed_component="/v1/payments",
            access_requirements="Authenticated",
            trust_boundary="DMZ",
        )
        db.add(surface)

        # 4. Threat Scenario
        threat = Threat(
            organization_id=o_uuid,
            audit_id=a_uuid,
            threat_id_code="THR-001",
            title="Stolen Credential Token Replay",
            description="Attacker captures administrative JWT token and replays against payment gateway.",
            stride_category="Spoofing",
            threat_category="Credential Access",
            severity="medium",
            risk_score=8,
            review_status="accepted",
        )
        db.add(threat)
        db.flush()

        # 5. Discovered Control & Assessment
        control = DiscoveredControl(
            organization_id=o_uuid,
            audit_id=a_uuid,
            control_code="CTL-001",
            name="Hardware Token MFA",
            description="Mandatory FIPS 140-2 Level 3 hardware security token enforcement.",
            category="access_control",
            evidence_maturity="implementation",
            implementation_status="documented",
            control_objective="Prevent unauthorized administrative access.",
        )
        db.add(control)
        db.flush()

        ctl_assess = ControlAssessment(
            organization_id=o_uuid,
            audit_id=a_uuid,
            control_id=control.id,
            status="effective_documented_control",
            review_status="approved",
        )
        db.add(ctl_assess)

        # 6. Finding
        finding = Finding(
            organization_id=o_uuid,
            audit_id=a_uuid,
            finding_code="GAP-001",
            title="Key Rotation Schedule Not Explicitly Documented",
            description="While AES-256 encryption is implemented, the documentation lacks automatic 90-day key rotation proof.",
            finding_category="control_weakness",
            evidence_state="confirmed_weakness",
            severity="low",
            risk_score=4,
            likelihood_score=2,
            impact_score=2,
            remediation_recommendation="Implement automated AWS KMS CMK key rotation and update architecture manual.",
            review_status="pending_review",
        )
        db.add(finding)

        # 7. Completed Adjudication Run
        adj_run = AdjudicationRun(
            organization_id=o_uuid,
            audit_id=a_uuid,
            status="completed",
            model_name="gemini-1.5-flash",
            requirements_processed_count=1,
            threats_processed_count=1,
            controls_processed_count=1,
            decisions_generated_count=2,
            contradictions_detected_count=1,
        )
        db.add(adj_run)
        db.flush()

        # Requirement Decision
        dec_req = AdjudicationDecision(
            organization_id=o_uuid,
            audit_id=a_uuid,
            adjudication_run_id=adj_run.id,
            decision_category="requirement_compliance",
            related_entity_type="requirement",
            related_entity_id=req.id,
            outcome_status="supported_by_documented_evidence",
            confidence_score=0.88,
            summary="Requirement PCI-REQ-8.3 is supported by implementation-level evidence in Payment_System_Architecture_v2.pdf.",
            reasoning="Hardware MFA tokens enforced for all administrative access.",
            review_status="approved",
            is_stale=False,
            is_provisional=False,
        )
        db.add(dec_req)
        db.flush()

        # Source reference
        src = AdjudicationSource(
            organization_id=o_uuid,
            audit_id=a_uuid,
            decision_id=dec_req.id,
            source_agent="defence_auditor",
            source_entity_type="discovered_control",
            source_entity_id=control.id,
            source_role="supporting",
            exact_excerpt="Hardware MFA tokens enforced on all administrative access.",
            is_citation_valid=True,
        )
        db.add(src)

        # Threat Decision
        dec_threat = AdjudicationDecision(
            organization_id=o_uuid,
            audit_id=a_uuid,
            adjudication_run_id=adj_run.id,
            decision_category="threat_mitigation",
            related_entity_type="threat",
            related_entity_id=threat.id,
            outcome_status="documented_mitigations_supported",
            confidence_score=0.85,
            summary="Threat THR-001 is mitigated by documented hardware token MFA.",
            reasoning="Enforced in DMZ access gateways.",
            review_status="approved",
            is_stale=False,
            is_provisional=False,
        )
        db.add(dec_threat)

        # Contradiction
        contradiction = AdjudicationContradiction(
            organization_id=o_uuid,
            audit_id=a_uuid,
            adjudication_run_id=adj_run.id,
            contradiction_category="requirement_vs_control",
            title="Session Timeout Discrepancy",
            description="Policy requires 15-minute session timeout while deployment guide notes 30 minutes.",
            conflicting_claims=[
                {"claim": "Policy mandates 15-minute administrative timeout."},
                {"claim": "Deployment blueprint documents 30-minute idle session timeout."},
            ],
            source_references=[],
            impact="Administrative sessions may remain active longer than permitted.",
            severity="medium",
            resolution_status="resolved",
            resolution_notes="Auditor confirmed 15-minute timeout enforced in IAM production configuration.",
        )
        db.add(contradiction)

        db.commit()
        return {
            "doc_id": str(doc.id),
            "chunk_id": str(chunk.id),
            "req_id": str(req.id),
            "threat_id": str(threat.id),
            "control_id": str(control.id),
            "finding_id": str(finding.id),
            "adj_run_id": str(adj_run.id),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_report_readiness_preflight(client: TestClient) -> None:
    """Test 1: Report readiness pre-flight check detects blockers and ready state."""
    user = create_auth_user(client, "Readiness Test Org")
    audit_id = create_sample_audit(client, user)

    # Initially: no adjudication run exists -> blocked
    res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports/readiness",
        headers=user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_ready"] is False
    assert len(data["blockers"]) >= 1
    assert data["adjudication_runs_count"] == 0

    # Populate data including completed adjudication run
    populate_audit_data_with_adjudication(audit_id, user["org_id"])

    # Now readiness should be ready
    res2 = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports/readiness",
        headers=user["headers"],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_ready"] is True
    assert len(data2["blockers"]) == 0
    assert data2["adjudication_runs_count"] >= 1
    assert data2["total_decisions_count"] >= 2


def test_full_report_generation_workflow(client: TestClient) -> None:
    """Test 2: Complete report generation pipeline produces valid PDF with all 12 sections."""
    user = create_auth_user(client, "Generation Test Org")
    audit_id = create_sample_audit(client, user)
    entities = populate_audit_data_with_adjudication(audit_id, user["org_id"])

    # Generate Report
    res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
        json={
            "adjudication_run_id": entities["adj_run_id"],
            "title": "Annual Production PCI-DSS Audit Report",
            "format": "pdf",
        },
    )
    assert res.status_code == 201
    rep = res.json()

    assert rep["title"] == "Annual Production PCI-DSS Audit Report"
    assert rep["version"] == 1
    assert rep["format"] == "pdf"
    assert rep["generation_status"] == "completed"
    assert rep["storage_path"] is not None
    assert rep["file_checksum"] is not None
    assert len(rep["file_checksum"]) == 64  # SHA-256 hex string
    assert rep["file_size"] > 1000  # Valid non-empty PDF
    assert rep["is_stale"] is False

    # Verify structured metadata contains all 12 sections
    meta = rep["report_metadata"]
    assert "cover_page" in meta
    assert "executive_summary" in meta
    assert "scope_and_methodology" in meta
    assert "regulatory_requirements" in meta
    assert "discovered_assets" in meta
    assert "attack_surfaces" in meta
    assert "threat_assessment" in meta
    assert "control_assessment" in meta
    assert "findings_register" in meta
    assert "contradictions_and_gaps" in meta
    assert "remediation_roadmap" in meta
    assert "limitations_and_disclaimers" in meta
    assert "appendix" in meta

    # Verify Executive Summary numbers
    ex = meta["executive_summary"]
    assert ex["total_requirements_assessed"] >= 1
    assert ex["supported_requirements_count"] >= 1
    assert ex["total_controls_documented"] >= 1
    assert ex["total_threats_modeled"] >= 1
    assert ex["mitigated_threats_count"] >= 1


def test_report_versioning_immutability(client: TestClient) -> None:
    """Test 3: Generating reports sequentially produces v1, v2 without overwriting v1."""
    user = create_auth_user(client, "Versioning Test Org")
    audit_id = create_sample_audit(client, user)
    entities = populate_audit_data_with_adjudication(audit_id, user["org_id"])

    # Generate v1
    res1 = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
        json={"adjudication_run_id": entities["adj_run_id"]},
    )
    assert res1.status_code == 201
    rep1 = res1.json()
    assert rep1["version"] == 1
    rep1_id = rep1["id"]

    # Generate v2
    res2 = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
        json={"adjudication_run_id": entities["adj_run_id"]},
    )
    assert res2.status_code == 201
    rep2 = res2.json()
    assert rep2["version"] == 2
    rep2_id = rep2["id"]
    assert rep1_id != rep2_id

    # List reports: both v2 and v1 should exist
    res_list = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
    )
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 2
    assert items[0]["version"] == 2
    assert items[1]["version"] == 1


def test_stale_decision_identification_in_report(client: TestClient) -> None:
    """Test 4: Reports accurately identify and disclose stale adjudication decisions."""
    user = create_auth_user(client, "Stale Report Test Org")
    audit_id = create_sample_audit(client, user)
    entities = populate_audit_data_with_adjudication(audit_id, user["org_id"])

    # Mark decision as stale in DB
    db = SessionLocal()
    try:
        dec = db.scalars(
            select(AdjudicationDecision).where(
                AdjudicationDecision.adjudication_run_id == uuid.UUID(entities["adj_run_id"])
            )
        ).first()
        assert dec is not None
        dec.is_stale = True
        db.commit()
    finally:
        db.close()

    # Generate Report
    res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
        json={"adjudication_run_id": entities["adj_run_id"]},
    )
    assert res.status_code == 201
    rep = res.json()
    assert rep["is_stale"] is True

    # Metadata reflects staleness
    assert rep["report_metadata"]["cover_page"]["is_stale"] is True
    assert rep["report_metadata"]["executive_summary"]["stale_decisions_count"] >= 1


def test_report_preview_and_pdf_download(client: TestClient) -> None:
    """Test 5: Report preview returns structured 12-section data and download returns valid PDF bytes."""
    user = create_auth_user(client, "Download Test Org")
    audit_id = create_sample_audit(client, user)
    entities = populate_audit_data_with_adjudication(audit_id, user["org_id"])

    # Generate Report
    res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports",
        headers=user["headers"],
        json={"adjudication_run_id": entities["adj_run_id"]},
    )
    assert res.status_code == 201
    report_id = res.json()["id"]

    # 1. Test Preview Endpoint
    res_prev = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports/{report_id}/preview",
        headers=user["headers"],
    )
    assert res_prev.status_code == 200
    prev_data = res_prev.json()
    assert prev_data["report_id"] == report_id
    assert prev_data["generation_status"] == "completed"
    assert "cover_page" in prev_data["data"]
    assert "regulatory_requirements" in prev_data["data"]

    # 2. Test PDF Download Endpoint
    res_down = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/reports/{report_id}/download",
        headers=user["headers"],
    )
    assert res_down.status_code == 200
    assert "application/pdf" in res_down.headers.get("content-type", "")
    pdf_bytes = res_down.content
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

    # Verify PyMuPDF can open and parse downloaded PDF bytes
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 3  # Multi-page publication-grade PDF


def test_cross_tenant_isolation_reports(client: TestClient) -> None:
    """Test 6: Cross-tenant isolation blocks unauthorized report listing, retrieval, and download."""
    user_a = create_auth_user(client, "Tenant A Org")
    user_b = create_auth_user(client, "Tenant B Org")
    audit_a = create_sample_audit(client, user_a)
    entities = populate_audit_data_with_adjudication(audit_a, user_a["org_id"])

    # Generate report in Tenant A
    res = client.post(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_a}/reports",
        headers=user_a["headers"],
        json={"adjudication_run_id": entities["adj_run_id"]},
    )
    assert res.status_code == 201
    rep_a_id = res.json()["id"]

    # Tenant B attempts to list Tenant A's reports -> 404 (Audit not found in org)
    res_b_list = client.get(
        f"/api/organizations/{user_b['org_id']}/audits/{audit_a}/reports",
        headers=user_b["headers"],
    )
    assert res_b_list.status_code == 404

    # Tenant B attempts to get Tenant A's report details -> 404
    res_b_get = client.get(
        f"/api/organizations/{user_b['org_id']}/audits/{audit_a}/reports/{rep_a_id}",
        headers=user_b["headers"],
    )
    assert res_b_get.status_code == 404

    # Tenant B attempts to download Tenant A's report -> 404
    res_b_down = client.get(
        f"/api/organizations/{user_b['org_id']}/audits/{audit_a}/reports/{rep_a_id}/download",
        headers=user_b["headers"],
    )
    assert res_b_down.status_code == 404
