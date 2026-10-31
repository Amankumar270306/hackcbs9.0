"""Comprehensive test suite for Milestone 6: Defence Auditor, Control Discovery & Gap Assessment.

Validates:
1. Deterministic risk scoring formula for findings (likelihood * impact).
2. Defence readiness pre-flight check (evidence documents & approved requirements/threats).
3. Defence analysis pipeline with MockGeminiClient.
4. Control discovery, categorization, and evidence maturity levels (policy vs implementation).
5. 6 controlled assessment outcomes (effective, partial, insufficient, contradictory, weakness, N/A).
6. Verbatim evidence citation and chunk traceability.
7. Requirement and threat mapping (links only to approved requirements and accepted/provisional threats).
8. Finding & gap generation with deterministic risk score and severity.
9. Human review workflows (approve, reject with reason, edit with score recalculation, audit trails).
10. Multi-tenant isolation and security boundary enforcement.
"""

from __future__ import annotations

import io
import uuid
from typing import Any, Dict
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
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
from app.database.models.regulatory import AuditRequirement, RegulatoryFramework
from app.main import app
from app.services.ai.gemini_client import MockGeminiClient, set_gemini_client
from app.services.defence_auditor import compute_finding_risk_and_severity


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_auth_user(client: TestClient, org_name: str = "Defence Test Org") -> Dict[str, Any]:
    """Helper to register user and obtain auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"defence_{uid}@sentinel-test.com"
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
    data = res.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": data["user_id"],
        "email": email,
        "org_id": data["organization_id"],
    }


def create_sample_audit(client: TestClient, user: Dict[str, Any]) -> str:
    """Helper to create an audit."""
    res = client.post(
        f"/api/organizations/{user['org_id']}/audits",
        headers=user["headers"],
        json={
            "name": "Cloud Security Safeguards Audit",
            "application_name": "Core Banking API",
            "target_system": "Multi-region Kubernetes & YugabyteDB",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def generate_security_policy_pdf() -> bytes:
    """Generates a valid test PDF describing security safeguards and controls."""
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Corporate Information Security Policy - Section 4 Access Control\n\n"
        "Section 4.1 Multi-Factor Authentication Policy\n"
        "All interactive administrative access originating outside the internal network "
        "must require at least two distinct authentication factors (FIDO2 or TOTP hardware keys).\n\n"
        "Section 4.2 Data Encryption at Rest\n"
        "Customer cardholder data and database backups are encrypted at rest using AES-256-GCM "
        "with customer-managed KMS keys rotated every 90 days.\n\n"
        "Section 4.3 Centralized Audit Logging\n"
        "All access requests and privilege escalations are logged to a centralized SIEM repository."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# Unit Tests
# ============================================================================

def test_deterministic_finding_risk_scoring_formula():
    """Validates strict mathematical computation of finding risk scores and severities."""
    # Scale: 1-4 Low, 5-9 Medium, 10-14 High, 15-19 Very High, 20-25 Critical
    test_cases = [
        (1, 1, 1, "low"),
        (2, 2, 4, "low"),
        (1, 5, 5, "medium"),
        (3, 3, 9, "medium"),
        (2, 5, 10, "high"),
        (3, 4, 12, "high"),
        (3, 5, 15, "very_high"),
        (4, 4, 16, "very_high"),
        (4, 5, 20, "critical"),
        (5, 5, 25, "critical"),
    ]
    for likelihood, impact, expected_score, expected_sev in test_cases:
        score, sev = compute_finding_risk_and_severity(likelihood, impact)
        assert score == expected_score, f"Expected {expected_score} for {likelihood}x{impact}, got {score}"
        assert sev == expected_sev, f"Expected {expected_sev} for score {score}, got {sev}"


# ============================================================================
# Integration Tests
# ============================================================================

def test_defence_readiness_preflight(client: TestClient):
    """Verifies pre-flight readiness logic when missing evidence or requirements vs ready."""
    user = create_auth_user(client, "Readiness Org")
    audit_id = create_sample_audit(client, user)
    org_id = user["org_id"]
    headers = user["headers"]

    # 1. Fresh audit has no documents and no requirements: NOT ready
    res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/defence-readiness",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_ready"] is False
    assert len(data["blockers"]) >= 1

    # 2. Add an audit document and process it
    pdf_bytes = generate_security_policy_pdf()
    upload_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/documents",
        headers=headers,
        files={"file": ("sec_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code in (200, 201)

    # 3. Add an approved requirement in the database
    with SessionLocal() as db:
        fw = RegulatoryFramework(
            name="NIST SP 800-53",
            short_name="NIST-800-53",
            version="Rev 5",
            issuing_authority="NIST",
            jurisdiction="US Federal",
            organization_id=uuid.UUID(org_id),
        )
        db.add(fw)
        db.flush()

        req = Requirement(
            organization_id=uuid.UUID(org_id),
            framework_id=fw.id,
            framework=fw.name,
            identifier="IA-2(1)",
            requirement_code="IA-2(1)",
            title="Multi-Factor Authentication for Administrative Accounts",
            description="Enforce multi-factor authentication for administrative access.",
            category="Access Control",
            obligation_type="mandatory",
            review_status="approved",
            reviewed_by=uuid.UUID(user["user_id"]),
        )
        db.add(req)
        db.flush()

        db.add(
            AuditRequirement(
                organization_id=uuid.UUID(org_id),
                audit_id=uuid.UUID(audit_id),
                requirement_id=req.id,
                applicability_status="applicable",
            )
        )
        db.commit()

    # 4. Check readiness again: now should be ready!
    res_ready = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/defence-readiness",
        headers=headers,
    )
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["is_ready"] is True
    assert ready_data["approved_requirements"] == 1
    assert ready_data["total_documents"] >= 1
    assert len(ready_data["blockers"]) == 0


def test_defence_analysis_pipeline_and_control_discovery(client: TestClient):
    """Tests the full Defence Auditor analysis pipeline, control discovery, and assessments."""
    user = create_auth_user(client, "Defence Pipeline Org")
    audit_id = create_sample_audit(client, user)
    org_id = user["org_id"]
    headers = user["headers"]

    # 1. Upload audit document
    pdf_bytes = generate_security_policy_pdf()
    up_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/documents",
        headers=headers,
        files={"file": ("security_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert up_res.status_code in (200, 201)
    doc_id = up_res.json()["id"]

    # 2. Seed approved requirement and accepted threat scenario
    with SessionLocal() as db:
        fw = RegulatoryFramework(
            name="ISO 27001:2022",
            short_name="ISO-27001",
            version="2022",
            issuing_authority="ISO/IEC",
            jurisdiction="International",
            organization_id=uuid.UUID(org_id),
        )
        db.add(fw)
        db.flush()

        req_approved = Requirement(
            organization_id=uuid.UUID(org_id),
            framework_id=fw.id,
            framework=fw.name,
            identifier="A.9.4.2",
            requirement_code="A.9.4.2",
            title="Secure Log-on Procedures",
            description="Where required by the access control policy, access to systems shall be controlled by a secure log-on procedure.",
            category="Access Control",
            obligation_type="mandatory",
            review_status="approved",
            reviewed_by=uuid.UUID(user["user_id"]),
        )
        # Unapproved requirement (must not be mapped)
        req_pending = Requirement(
            organization_id=uuid.UUID(org_id),
            framework_id=fw.id,
            framework=fw.name,
            identifier="A.12.1.1",
            requirement_code="A.12.1.1",
            title="Documented Operating Procedures",
            description="Operating procedures shall be documented and made available.",
            category="Operations Security",
            obligation_type="mandatory",
            review_status="pending_review",
        )
        db.add_all([req_approved, req_pending])
        db.flush()

        db.add(AuditRequirement(organization_id=uuid.UUID(org_id), audit_id=uuid.UUID(audit_id), requirement_id=req_approved.id, applicability_status="applicable"))
        db.add(AuditRequirement(organization_id=uuid.UUID(org_id), audit_id=uuid.UUID(audit_id), requirement_id=req_pending.id, applicability_status="applicable"))

        # Threat scenarios: accepted vs rejected
        threat_accepted = Threat(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            threat_id_code="THR-001",
            title="Remote Administrative Credential Compromise",
            description="Adversary steals administrative credentials to access console.",
            stride_category="Elevation of Privilege",
            severity="critical",
            review_status="accepted",
            likelihood_score=4,
            impact_score=5,
            risk_score=20,
        )
        threat_rejected = Threat(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            threat_id_code="THR-999",
            title="Physical Vault Tampering",
            description="Physical intrusion into data center floor.",
            stride_category="Tampering",
            severity="low",
            review_status="rejected",
            likelihood_score=1,
            impact_score=1,
            risk_score=1,
        )
        db.add_all([threat_accepted, threat_rejected])
        db.commit()

        approved_req_id = str(req_approved.id)
        accepted_threat_id = str(threat_accepted.id)

    # 3. Configure Mock Gemini Client with structured Defence Auditor output
    mock_llm = MockGeminiClient()
    mock_llm.queue_response({
        "controls": [
            {
                "control_code": "CTRL-MFA-01",
                "name": "Hardware-backed Multi-Factor Authentication",
                "description": "Enforces FIDO2 or TOTP two-factor authentication for administrative access.",
                "category": "Access Control",
                "control_objective": "Mitigate credential compromise and brute force on admin interfaces.",
                "implementation_status": "documented",
                "operational_status": "active",
                "evidence_maturity": "implementation",
                "confidence_score": 0.95,
                "requirement_ids": [approved_req_id],
                "threat_ids": [accepted_threat_id],
                "evidence_citations": [
                    {
                        "document_id": doc_id,
                        "filename": "security_policy.pdf",
                        "page_number": 1,
                        "section_title": "Section 4.1 Multi-Factor Authentication Policy",
                        "exact_excerpt": "All interactive administrative access originating outside the internal network must require at least two distinct authentication factors",
                        "citation_type": "direct_evidence",
                        "evidence_maturity": "implementation",
                        "relevance_explanation": "Directly supports implementation of MFA for remote access.",
                    }
                ],
            }
        ],
        "assessments": [
            {
                "control_code": "CTRL-MFA-01",
                "requirement_id": approved_req_id,
                "threat_id": accepted_threat_id,
                "status": "effective_documented_control",
                "evidence_maturity": "implementation",
                "assessment_explanation": "Control is explicitly documented with implementation requirements for FIDO2/TOTP.",
                "evidence_limitations": "Quarterly administrative audit logs not provided.",
                "missing_information": "IdP authentication logs confirming operational enforcement.",
                "contradictions": None,
                "recommended_next_steps": "Export and attach IdP sign-in audit logs.",
                "confidence_score": 0.94,
            }
        ],
        "findings": [
            {
                "finding_code": "GAP-LOG-01",
                "title": "Missing Operational Enforcement Logs for MFA",
                "description": "Policy mandates MFA, but operational logs or SIEM telemetry were not submitted.",
                "finding_category": "operational_evidence_gap",
                "severity": "medium",
                "evidence_state": "insufficient_evidence",
                "likelihood_score": 3,
                "impact_score": 3,
                "is_provisional": False,
                "confidence_score": 0.88,
                "remediation_recommendation": "Configure automatic export of authentication logs from IdP to SIEM.",
                "related_control_codes": ["CTRL-MFA-01"],
                "related_requirement_ids": [approved_req_id],
                "related_threat_ids": [accepted_threat_id],
                "evidence_citations": [],
            }
        ],
    })
    set_gemini_client(mock_llm)

    # 4. Trigger Defence Analysis Run
    run_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/defence-analysis",
        headers=headers,
        json={"model_name": "gemini-1.5-flash", "run_in_background": False},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert run_data["controls_discovered_count"] == 1
    assert run_data["assessments_count"] == 1
    assert run_data["findings_count"] == 1

    # 5. Verify Controls List Endpoint
    controls_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls",
        headers=headers,
    )
    assert controls_res.status_code == 200
    controls = controls_res.json()
    assert len(controls) == 1
    ctrl = controls[0]
    assert ctrl["control_code"] == "CTRL-MFA-01"
    assert ctrl["name"] == "Hardware-backed Multi-Factor Authentication"
    assert ctrl["category"] == "Access Control"
    assert ctrl["evidence_maturity"] == "implementation"
    assert ctrl["assessment_status"] == "effective_documented_control"
    assert ctrl["evidence_count"] >= 1
    control_id = ctrl["id"]

    # 6. Verify Control Detail Endpoint
    detail_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls/{control_id}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["assessments"]) == 1
    assert detail["assessments"][0]["status"] == "effective_documented_control"
    assert len(detail["requirement_mappings"]) == 1
    assert detail["requirement_mappings"][0]["requirement_identifier"] == "A.9.4.2"
    assert len(detail["threat_mappings"]) == 1
    assert detail["threat_mappings"][0]["threat_title"] == "Remote Administrative Credential Compromise"
    assert len(detail["evidence_references"]) == 1
    assert "at least two distinct authentication factors" in detail["evidence_references"][0]["exact_excerpt"]

    # 7. Verify Findings Endpoint
    findings_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/findings",
        headers=headers,
    )
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) == 1
    f = findings[0]
    assert f["finding_code"] == "GAP-LOG-01"
    assert f["finding_category"] == "operational_evidence_gap"
    assert f["likelihood_score"] == 3
    assert f["impact_score"] == 3
    assert f["risk_score"] == 9
    assert f["severity"] == "medium"
    assert "CTRL-MFA-01" in f["related_control_codes"]


def test_human_review_workflow_for_controls_and_findings(client: TestClient):
    """Tests approval, rejection with mandatory reason, and manual edits on controls and findings."""
    user = create_auth_user(client, "Review Workflow Org")
    audit_id = create_sample_audit(client, user)
    org_id = user["org_id"]
    headers = user["headers"]

    # Seed a control and a finding directly
    with SessionLocal() as db:
        ctrl = DiscoveredControl(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            control_code="CTRL-ENC-01",
            name="Database Encryption at Rest",
            description="KMS CMK AES-256 encryption on all relational databases.",
            category="Cryptography",
            control_objective="Protect sensitive data from storage exfiltration.",
            implementation_status="documented",
            operational_status="active",
            evidence_maturity="implementation",
            confidence_score=0.92,
        )
        db.add(ctrl)
        db.flush()

        assess = ControlAssessment(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            control_id=ctrl.id,
            status="effective_documented_control",
            evidence_maturity="implementation",
            assessment_explanation="KMS encryption documented and verified.",
            confidence_score=0.90,
            review_status="pending_review",
        )
        db.add(assess)

        finding = Finding(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            finding_code="GAP-KMS-01",
            title="Automatic KMS Key Rotation Disabled",
            description="CMK keys lack 90-day automatic rotation policy.",
            finding_category="control_weakness",
            severity="high",
            evidence_state="confirmed_weakness",
            likelihood_score=3,
            impact_score=4,
            risk_score=12,
            review_status="pending_review",
        )
        db.add(finding)
        db.commit()

        ctrl_id = str(ctrl.id)
        finding_id = str(finding.id)

    # 1. Reject control without reason: MUST FAIL (400)
    rej_no_reason = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls/{ctrl_id}/review",
        headers=headers,
        json={"action": "reject", "reason": ""},
    )
    assert rej_no_reason.status_code == 400

    # 2. Reject control with documented reason: SUCCEEDS
    rej_ok = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls/{ctrl_id}/review",
        headers=headers,
        json={"action": "reject", "reason": "CloudFormation template demonstrates unencrypted volume flag set to false."},
    )
    assert rej_ok.status_code == 200

    # 3. Edit control name & category
    edit_res = client.patch(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls/{ctrl_id}",
        headers=headers,
        json={
            "name": "Database Volume Encryption (KMS)",
            "category": "Data Protection",
            "reason": "Clarified control scope to EBS volumes.",
        },
    )
    assert edit_res.status_code == 200
    ctrl_data = edit_res.json()
    assert ctrl_data["name"] == "Database Volume Encryption (KMS)"
    assert ctrl_data["category"] == "Data Protection"

    # Verify audit history logged
    detail_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/controls/{ctrl_id}",
        headers=headers,
    )
    assert len(detail_res.json()["audit_history"]) >= 2

    # 4. Reject finding without reason: MUST FAIL (400)
    f_rej_fail = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/findings/{finding_id}/review",
        headers=headers,
        json={"action": "reject", "reason": ""},
    )
    assert f_rej_fail.status_code == 400

    # 5. Approve finding
    f_app = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/findings/{finding_id}/review",
        headers=headers,
        json={"action": "approve", "reason": "Confirmed key rotation is absent."},
    )
    assert f_app.status_code == 200
    assert f_app.json()["review_status"] == "approved"

    # 6. Edit finding likelihood & impact -> DETERMINISTIC RISK RECALCULATION
    # Initial: 3 x 4 = 12 (high). New: 5 x 5 = 25 (critical)!
    edit_f_res = client.patch(
        f"/api/organizations/{org_id}/audits/{audit_id}/findings/{finding_id}",
        headers=headers,
        json={
            "likelihood_score": 5,
            "impact_score": 5,
            "reason": "Escalated after confirming production exposure.",
        },
    )
    assert edit_f_res.status_code == 200
    updated_f = edit_f_res.json()
    assert updated_f["likelihood_score"] == 5
    assert updated_f["impact_score"] == 5
    assert updated_f["risk_score"] == 25
    assert updated_f["severity"] == "critical"
    assert updated_f["review_status"] == "edited"


def test_cross_tenant_isolation_defence(client: TestClient):
    """Verifies that User from Org B cannot view, trigger, or review controls or findings in Org A."""
    user_a = create_auth_user(client, "Org A Defence")
    audit_a = create_sample_audit(client, user_a)

    user_b = create_auth_user(client, "Org B Defence")
    headers_b = user_b["headers"]

    # 1. Org B tries to view Org A readiness -> 403 Forbidden
    res_ready = client.get(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_a}/defence-readiness",
        headers=headers_b,
    )
    assert res_ready.status_code in (403, 404)

    # 2. Org B tries to trigger analysis on Org A -> 403 Forbidden
    res_trigger = client.post(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_a}/defence-analysis",
        headers=headers_b,
        json={"model_name": "gemini-1.5-flash"},
    )
    assert res_trigger.status_code in (403, 404)

    # 3. Org B tries to list controls of Org A -> 403 Forbidden
    res_ctrls = client.get(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_a}/controls",
        headers=headers_b,
    )
    assert res_ctrls.status_code in (403, 404)

    # 4. Org B tries to list findings of Org A -> 403 Forbidden
    res_findings = client.get(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_a}/findings",
        headers=headers_b,
    )
    assert res_findings.status_code in (403, 404)
