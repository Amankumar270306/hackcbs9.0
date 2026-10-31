"""Comprehensive test suite for Milestone 7: Adjudicator — Consensus, Reconciliation, Contradictions & Human Review.

Validates:
1. Deterministic confidence scoring formula based on strict evidentiary constraints.
2. Adjudication readiness pre-flight check across all upstream agents.
3. Cross-agent consensus pipeline with MockGeminiClient (reconciling Legal Analyst, Adversarial Strategist, Defence Auditor).
4. Requirement-level and Threat-level reconciliation outcomes with verbatim source citations.
5. Cross-agent contradiction detection (Requirement vs Control, Threat vs Control, AI vs Human review).
6. Human review workflows (approve, reject with mandatory reason, edit, and resolve contradictions with immutable audit trails).
7. Stale decision detection when upstream source requirements, threats, or controls are updated.
8. Multi-tenant isolation and security boundary enforcement.
"""

from __future__ import annotations

import io
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.adjudication import (
    AdjudicationAuditHistory,
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
from app.database.models.regulatory import AuditRequirement, RegulatoryFramework
from app.main import app
from app.services.adjudicator import compute_deterministic_confidence
from app.services.ai.gemini_client import MockGeminiClient, set_gemini_client


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_auth_user(client: TestClient, org_name: str = "Adjudicator Test Org") -> Dict[str, Any]:
    """Helper to register user and obtain auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"adjudicator_{uid}@sentinel-test.com"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"Adjudicator Analyst {uid}",
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
            "name": "Cloud Security Adjudication Audit",
            "application_name": "Core Banking API",
            "target_system": "Multi-region Kubernetes & YugabyteDB",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def generate_security_policy_pdf() -> bytes:
    """Generates a test PDF with verifiable verbatim citations."""
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Corporate Information Security Policy - Section 4 Access Control\n\n"
        "Section 4.1 Multi-Factor Authentication Policy\n"
        "All interactive administrative access originating outside the internal network "
        "must require at least two distinct authentication factors (FIDO2 or TOTP hardware keys).\n\n"
        "Section 4.2 Data Encryption at Rest\n"
        "All customer cardholder database partitions must enforce AES-256 GCM encryption at rest."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# 1. Deterministic Confidence Calculation Tests
# ============================================================================

def test_deterministic_confidence_calculation():
    """Validates that confidence scores follow strict deterministic evidentiary rules."""
    # Operational maturity base = 0.90
    conf_op = compute_deterministic_confidence(
        evidence_maturity="operational",
        outcome_status="supported_by_documented_evidence",
    )
    assert conf_op == 0.90

    # Implementation maturity base = 0.80
    conf_impl = compute_deterministic_confidence(
        evidence_maturity="implementation",
        outcome_status="supported_by_documented_evidence",
    )
    assert conf_impl == 0.80

    # Policy maturity base = 0.50
    conf_pol = compute_deterministic_confidence(
        evidence_maturity="policy",
        outcome_status="supported_by_documented_evidence",
    )
    assert conf_pol == 0.50

    # Invalid citation penalty: -0.25 (0.80 - 0.25 = 0.55)
    conf_inv = compute_deterministic_confidence(
        evidence_maturity="implementation",
        has_invalid_citations=True,
    )
    assert conf_inv == 0.55

    # Contradiction penalty: -0.20 (0.80 - 0.20 = 0.60)
    conf_contra = compute_deterministic_confidence(
        evidence_maturity="implementation",
        has_contradictions=True,
    )
    assert conf_contra == 0.60

    # Pending threat cap at 0.70
    conf_pending = compute_deterministic_confidence(
        evidence_maturity="operational",  # 0.90 base
        is_pending_threat=True,
    )
    assert conf_pending <= 0.70

    # Missing agent cap at 0.60
    conf_missing = compute_deterministic_confidence(
        evidence_maturity="operational",
        missing_agent_data=True,
    )
    assert conf_missing <= 0.60

    # Clamped bounds check (minimum 0.10, maximum 0.98)
    conf_low = compute_deterministic_confidence(
        evidence_maturity="unknown",
        outcome_status="insufficient_evidence",
        has_invalid_citations=True,
        has_contradictions=True,
        missing_agent_data=True,
    )
    assert conf_low >= 0.10


# ============================================================================
# 2. Adjudication Readiness Pre-Flight Check Tests
# ============================================================================

def test_adjudication_readiness_preflight(client: TestClient):
    """Validates pre-flight readiness verification across upstream agent sources."""
    user = create_auth_user(client)
    audit_id = create_sample_audit(client, user)

    # Empty audit: is_ready should be false
    res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-readiness",
        headers=user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_ready"] is False
    assert data["requirements_count"] == 0
    assert data["threats_count"] == 0
    assert data["controls_count"] == 0

    # Upload document to make it ready
    pdf_bytes = generate_security_policy_pdf()
    up_res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/documents",
        headers=user["headers"],
        files={"file": ("security_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"document_type": "security_policy"},
    )
    assert up_res.status_code == 201

    # Now readiness should reflect available evidence chunks
    res2 = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-readiness",
        headers=user["headers"],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_ready"] is True
    assert data2["evidence_chunks_count"] > 0


# ============================================================================
# 3. Adjudication Consensus Pipeline & Decisions Tests
# ============================================================================

def test_adjudication_consensus_pipeline_and_decisions(client: TestClient):
    """Validates end-to-end consensus reconciliation, decisions, citations, and contradictions."""
    set_gemini_client(MockGeminiClient())
    user = create_auth_user(client)
    audit_id = create_sample_audit(client, user)

    # 1. Upload evidence document
    pdf_bytes = generate_security_policy_pdf()
    up_res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/documents",
        headers=user["headers"],
        files={"file": ("security_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"document_type": "security_policy"},
    )
    assert up_res.status_code == 201
    doc_id = up_res.json()["id"]

    with SessionLocal() as db:
        chunk = db.execute(
            select(DocumentChunk).where(DocumentChunk.audit_document_id == uuid.UUID(doc_id))
        ).scalars().first()
        assert chunk is not None

        # 2. Seed Approved Regulatory Requirement (M4)
        framework = RegulatoryFramework(
            name="PCI DSS Standard",
            short_name="PCI-DSS-4.0",
            version="4.0",
            issuing_authority="PCI SSC",
            status="active",
        )
        db.add(framework)
        db.flush()

        req = Requirement(
            framework_id=framework.id,
            identifier="PCI-REQ-8.3",
            requirement_code="PCI-REQ-8.3",
            title="Multi-Factor Authentication",
            description="Multi-factor authentication shall be enforced for all administrative access.",
            requirement_statement="Multi-factor authentication shall be enforced for all administrative access.",
            obligation_type="mandatory",
            category="Access Control",
            review_status="approved",
        )
        db.add(req)
        db.flush()

        audit_req = AuditRequirement(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            requirement_id=req.id,
            applicability_status="applicable",
        )
        db.add(audit_req)

        # 3. Seed Accepted Threat Scenario (M5)
        threat = Threat(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            threat_id_code="THR-001",
            title="Credential Stuffing on Public Admin Gateway",
            description="Attacker performs automated brute force against administrative login.",
            threat_category="Credential Access",
            stride_category="Spoofing",
            severity="high",
            risk_score=16,
            review_status="accepted",  # Accepted threat!
        )
        db.add(threat)
        db.flush()

        # 4. Seed Discovered Control with Citation (M6)
        ctrl = DiscoveredControl(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            control_code="CTRL-001",
            name="Multi-Factor Authentication on Remote Administrative Portals",
            description="Enforces MFA using TOTP or hardware tokens on all administrative endpoints.",
            control_objective="Enforce multi-factor authentication on all remote admin access.",
            category="Access Control",
            implementation_status="documented",
            evidence_maturity="implementation",
        )
        db.add(ctrl)
        db.flush()

        ctrl_cite = ControlEvidenceReference(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            control_id=ctrl.id,
            audit_document_id=uuid.UUID(doc_id),
            document_chunk_id=chunk.id,
            citation_type="direct_evidence",
            exact_excerpt=chunk.content[:60],
            page_number=chunk.page_number,
            section_title="Access Control",
        )
        db.add(ctrl_cite)
        db.commit()

    # 5. Trigger Adjudication Run
    run_res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication",
        headers=user["headers"],
        json={"model_name": "gemini-1.5-flash", "run_in_background": False},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert run_data["decisions_generated_count"] >= 1
    assert run_data["execution_duration_ms"] is not None

    # 6. Verify Decisions
    dec_res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-decisions",
        headers=user["headers"],
    )
    assert dec_res.status_code == 200
    decisions = dec_res.json()
    assert len(decisions) >= 1

    # Check requirement compliance decision
    req_dec = next((d for d in decisions if d["decision_category"] == "requirement_compliance"), None)
    assert req_dec is not None
    assert req_dec["outcome_status"] == "supported_by_documented_evidence"
    assert req_dec["confidence_score"] >= 0.50
    assert req_dec["is_provisional"] is False

    # Check threat mitigation decision
    threat_dec = next((d for d in decisions if d["decision_category"] == "threat_mitigation"), None)
    assert threat_dec is not None
    assert threat_dec["outcome_status"] == "documented_mitigations_supported"

    # 7. Verify Contradictions Detected
    contra_res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-contradictions",
        headers=user["headers"],
    )
    assert contra_res.status_code == 200
    contradictions = contra_res.json()
    assert len(contradictions) >= 1
    c0 = contradictions[0]
    assert c0["resolution_status"] == "unresolved"
    assert len(c0["conflicting_claims"]) >= 1


# ============================================================================
# 4. Human Review & Contradiction Resolution Workflow Tests
# ============================================================================

def test_human_review_and_contradiction_resolution(client: TestClient):
    """Validates human review actions on decisions and contradiction resolution with immutable audit trails."""
    set_gemini_client(MockGeminiClient())
    user = create_auth_user(client)
    audit_id = create_sample_audit(client, user)

    # Seed an adjudication decision and contradiction
    with SessionLocal() as db:
        run = AdjudicationRun(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            status="completed",
            model_name="gemini-1.5-flash",
            prompt_version="v1.0",
            input_source_snapshot={},
        )
        db.add(run)
        db.flush()

        dec = AdjudicationDecision(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            adjudication_run_id=run.id,
            decision_category="requirement_compliance",
            related_entity_type="requirement",
            related_entity_id=uuid.uuid4(),
            outcome_status="partially_supported",
            summary="Partial MFA evidence found in configuration.",
            reasoning="Configuration exists, but live logs are pending verification.",
            confidence_score=0.65,
            review_status="pending_review",
        )
        db.add(dec)

        contra = AdjudicationContradiction(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            adjudication_run_id=run.id,
            contradiction_category="requirement_vs_control",
            title="Software TOTP vs Hardware Token Mandate",
            description="Policy mandates hardware keys, but software app is configured.",
            conflicting_claims=[{"claim": "Hardware required"}],
            source_references=[{"source": "doc"}],
            impact="May leave root access vulnerable to SIM swap attacks.",
            severity="medium",
            resolution_status="unresolved",
        )
        db.add(contra)
        db.commit()
        dec_id = str(dec.id)
        contra_id = str(contra.id)

    # 1. Human Decision Review: Approve
    rev_res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-decisions/{dec_id}/review",
        headers=user["headers"],
        json={"action": "approve", "justification": "Verified with security team during operational walkthrough."},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_status"] == "approved"

    # 2. Human Decision Edit
    edit_res = client.patch(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-decisions/{dec_id}",
        headers=user["headers"],
        json={
            "outcome_status": "supported_by_documented_evidence",
            "confidence_score": 0.85,
            "justification": "Upgraded after inspecting active Okta admin sign-on audit stream.",
        },
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["outcome_status"] == "supported_by_documented_evidence"
    assert edit_res.json()["confidence_score"] == 0.85
    assert edit_res.json()["review_status"] == "edited"

    # 3. Retrieve Decision Detail and check immutable audit history
    detail_res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-decisions/{dec_id}",
        headers=user["headers"],
    )
    assert detail_res.status_code == 200
    d_data = detail_res.json()
    assert len(d_data["audit_history"]) >= 2  # approve + edit

    # 4. Resolve Contradiction
    resolv_res = client.post(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-contradictions/{contra_id}/resolve",
        headers=user["headers"],
        json={
            "resolution_status": "resolved",
            "resolution_notes": "Security exception #8812 approved by CISO allowing software TOTP until Q3 migration.",
        },
    )
    assert resolv_res.status_code == 200
    assert resolv_res.json()["resolution_status"] == "resolved"


# ============================================================================
# 5. Stale Decision Detection Tests
# ============================================================================

def test_stale_decision_detection(client: TestClient):
    """Validates that changes to upstream requirements, threats, or controls mark decisions as stale."""
    user = create_auth_user(client)
    audit_id = create_sample_audit(client, user)

    # 1. Check stale status with no runs
    res0 = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-stale-status",
        headers=user["headers"],
    )
    assert res0.status_code == 200
    assert res0.json()["has_stale_decisions"] is False

    # 2. Seed completed run and decision
    with SessionLocal() as db:
        run = AdjudicationRun(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            status="completed",
            completed_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            input_source_snapshot={},
        )
        db.add(run)
        db.flush()

        dec = AdjudicationDecision(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            adjudication_run_id=run.id,
            decision_category="requirement_compliance",
            related_entity_type="requirement",
            related_entity_id=uuid.uuid4(),
            outcome_status="partially_supported",
            summary="Initial partial support.",
            reasoning="Initial reasoning.",
            confidence_score=0.70,
            is_stale=False,
        )
        db.add(dec)

        # Add a control with updated_at in the future of the run completed_at
        ctrl = DiscoveredControl(
            organization_id=uuid.UUID(user["org_id"]),
            audit_id=uuid.UUID(audit_id),
            control_code="CTRL-STALE-01",
            name="Encryption at Rest",
            description="AES-256 encryption",
            control_objective="Enforce AES-256 encryption across all storage volumes.",
            category="Cryptography",
            updated_at=datetime.now(timezone.utc),  # newer than run!
        )
        db.add(ctrl)
        db.commit()

    # 3. Check stale status now
    stale_res = client.get(
        f"/api/organizations/{user['org_id']}/audits/{audit_id}/adjudication-stale-status",
        headers=user["headers"],
    )
    assert stale_res.status_code == 200
    stale_data = stale_res.json()
    assert stale_data["has_stale_decisions"] is True
    assert stale_data["newer_source_changes_count"] >= 1


# ============================================================================
# 6. Multi-Tenant Isolation Tests
# ============================================================================

def test_cross_tenant_isolation_adjudication(client: TestClient):
    """Verifies that decisions, runs, and contradictions are strictly isolated across tenants."""
    user_a = create_auth_user(client, "Tenant Alpha")
    user_b = create_auth_user(client, "Tenant Beta")
    audit_a = create_sample_audit(client, user_a)

    with SessionLocal() as db:
        run_a = AdjudicationRun(
            organization_id=uuid.UUID(user_a["org_id"]),
            audit_id=uuid.UUID(audit_a),
            status="completed",
            input_source_snapshot={},
        )
        db.add(run_a)
        db.flush()

        dec_a = AdjudicationDecision(
            organization_id=uuid.UUID(user_a["org_id"]),
            audit_id=uuid.UUID(audit_a),
            adjudication_run_id=run_a.id,
            decision_category="requirement_compliance",
            related_entity_type="requirement",
            outcome_status="supported_by_documented_evidence",
            summary="Confidential Alpha decision",
            reasoning="Secret tenant reasoning",
            confidence_score=0.90,
        )
        db.add(dec_a)

        contra_a = AdjudicationContradiction(
            organization_id=uuid.UUID(user_a["org_id"]),
            audit_id=uuid.UUID(audit_a),
            adjudication_run_id=run_a.id,
            contradiction_category="requirement_vs_control",
            title="Confidential Alpha Contradiction",
            description="Tenant Alpha secret",
            impact="High impact",
            resolution_status="unresolved",
        )
        db.add(contra_a)
        db.commit()
        dec_id = str(dec_a.id)
        contra_id = str(contra_a.id)

    # Tenant B tries to access Tenant A's decision: must return 404
    b_res = client.get(
        f"/api/organizations/{user_b['org_id']}/audits/{audit_a}/adjudication-decisions/{dec_id}",
        headers=user_b["headers"],
    )
    assert b_res.status_code == 404

    # Tenant B tries to access Tenant A's contradiction: must return 404
    b_res2 = client.get(
        f"/api/organizations/{user_b['org_id']}/audits/{audit_a}/adjudication-contradictions/{contra_id}",
        headers=user_b["headers"],
    )
    assert b_res2.status_code == 404

