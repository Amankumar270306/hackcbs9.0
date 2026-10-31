"""Comprehensive test suite for Milestone 5: Adversarial Strategist & Threat Analysis.

Validates:
1. Threat analysis readiness pre-flight check.
2. Asset discovery and data classification (documented vs inferred).
3. Attack surface entry points, trust boundaries, and exposure.
4. STRIDE threat generation & CIA impact ratings with MockGeminiClient.
5. Strict deterministic risk scoring (likelihood * impact) and severity mapping.
6. Multi-step attack tree decomposition (root objectives, steps, logical operators).
7. Regulatory mapping (links only to approved requirements, excludes pending).
8. Evidence traceability and verbatim chunk excerpt validation.
9. Human review workflow (accept, reject with reason, edit, request info, audit trail).
10. Multi-tenant isolation and RBAC security boundaries.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.assessments import Requirement, Threat
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.regulatory import AuditRequirement, RegulatoryFramework
from app.database.models.threats import (
    AttackPathNode,
    AttackSurface,
    DiscoveredAsset,
    ThreatAnalysisRun,
    ThreatAuditHistory,
)
from app.main import app
from app.services.adversarial_strategist import compute_risk_and_severity
from app.services.ai.gemini_client import MockGeminiClient, set_gemini_client


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_auth_user(client: TestClient, org_name: str = "Threat Test Org") -> Dict[str, Any]:
    """Helper to register user and obtain auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"threat_{uid}@sentinel-test.com"
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
            "name": "Cloud Payment Gateway Audit",
            "application_name": "Payment API",
            "target_system": "Multi-region Kubernetes & YugabyteDB",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def generate_architecture_pdf() -> bytes:
    """Generates a valid test PDF describing system architecture and security controls."""
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Payment Architecture Document - Page 1\n\n"
        "Section 1.1 Architecture Overview\n"
        "The system exposes a Public REST Auth API at /api/v1/auth/login for token generation. "
        "User credentials and sensitive credit card numbers are stored in the Customer Authentication Database. "
        "The web application accepts unauthenticated incoming traffic from the public Internet.\n\n"
        "Section 1.2 Data Storage and Boundaries\n"
        "Production databases reside in an isolated VPC behind a DMZ gateway. "
        "Credit card numbers are encrypted using AES-256 keys managed in KMS."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# 1. Deterministic Risk Scoring Unit Tests
# ============================================================================

def test_deterministic_risk_scoring_formula():
    """Verify strictly that risk_score = likelihood * impact with exact severity mapping."""
    # Test boundary 1: Low (1-4)
    score, sev = compute_risk_and_severity(1, 1)
    assert score == 1 and sev == "low"
    score, sev = compute_risk_and_severity(2, 2)
    assert score == 4 and sev == "low"

    # Test boundary 2: Medium (5-9)
    score, sev = compute_risk_and_severity(1, 5)
    assert score == 5 and sev == "medium"
    score, sev = compute_risk_and_severity(3, 3)
    assert score == 9 and sev == "medium"

    # Test boundary 3: High (10-14)
    score, sev = compute_risk_and_severity(2, 5)
    assert score == 10 and sev == "high"
    score, sev = compute_risk_and_severity(3, 4)
    assert score == 12 and sev == "high"

    # Test boundary 4: Very High (15-19)
    score, sev = compute_risk_and_severity(3, 5)
    assert score == 15 and sev == "very_high"
    score, sev = compute_risk_and_severity(4, 4)
    assert score == 16 and sev == "very_high"

    # Test boundary 5: Critical (20-25)
    score, sev = compute_risk_and_severity(4, 5)
    assert score == 20 and sev == "critical"
    score, sev = compute_risk_and_severity(5, 5)
    assert score == 25 and sev == "critical"

    # Clamping test for inputs outside 1-5
    score, sev = compute_risk_and_severity(0, 10)
    assert score == 5 and sev == "medium"  # 1 * 5 = 5


# ============================================================================
# 2. Readiness Pre-Flight Check Tests
# ============================================================================

def test_threat_readiness_preflight(client: TestClient):
    """Test readiness check reports not ready when documents or approved reqs are missing."""
    user = create_auth_user(client, "Readiness Org")
    headers = user["headers"]
    org_id = user["org_id"]
    audit_id = create_sample_audit(client, user)

    # 1. Initially without docs or requirements
    res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/threat-readiness",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_ready"] is False
    assert data["documents_count"] == 0
    assert data["approved_requirements_count"] == 0
    assert len(data["validation_messages"]) >= 2


# ============================================================================
# 3. Full Threat Analysis Pipeline with Mock Client
# ============================================================================

def test_adversarial_threat_analysis_pipeline(client: TestClient):
    """Test end-to-end threat analysis execution, asset discovery, attack surfaces, STRIDE threats, and trees."""
    user = create_auth_user(client, "Adversarial Pipeline Org")
    headers = user["headers"]
    org_id = user["org_id"]
    audit_id = create_sample_audit(client, user)

    # 1. Upload audit evidence document and process chunks
    pdf_bytes = generate_architecture_pdf()
    up_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/documents",
        headers=headers,
        files={"file": ("payment_architecture.pdf", pdf_bytes, "application/pdf")},
    )
    assert up_res.status_code == 201
    doc_id = up_res.json()["id"]

    # 2. Add an approved requirement and a pending requirement
    with SessionLocal() as db:
        fw = RegulatoryFramework(
            name="PCI-DSS v4.0 Threat Test",
            short_name="PCI-DSS-4.0",
            version="4.0",
            framework_type="standard",
            issuing_authority="PCI SSC",
            jurisdiction="Global",
            status="active",
            organization_id=uuid.UUID(org_id),
        )
        db.add(fw)
        db.flush()

        # Approved requirement (must be included in threat mapping)
        req_approved = Requirement(
            framework_id=fw.id,
            framework=fw.name,
            identifier="REQ-PCI-3.4",
            requirement_code="REQ-PCI-3.4",
            title="Render Primary Account Numbers (PAN) Unreadable",
            description="PAN must be rendered unreadable anywhere it is stored using strong cryptography.",
            requirement_statement="PAN must be rendered unreadable anywhere it is stored using strong cryptography.",
            category="Data Protection & Encryption",
            obligation_type="mandatory",
            review_status="approved",
            reviewed_by=uuid.UUID(user["user_id"]),
        )
        db.add(req_approved)

        # Pending requirement (must NOT be mapped)
        req_pending = Requirement(
            framework_id=fw.id,
            framework=fw.name,
            identifier="REQ-PCI-8.3",
            requirement_code="REQ-PCI-8.3",
            title="Multi-factor Authentication for Console Access",
            description="MFA is required for all non-console administrative access.",
            requirement_statement="MFA is required for all non-console administrative access.",
            category="Identity and Access Management",
            obligation_type="mandatory",
            review_status="pending_review",
        )
        db.add(req_pending)
        db.flush()

        # Map both to audit
        db.add(AuditRequirement(organization_id=uuid.UUID(org_id), audit_id=uuid.UUID(audit_id), requirement_id=req_approved.id, applicability_status="applicable"))
        db.add(AuditRequirement(organization_id=uuid.UUID(org_id), audit_id=uuid.UUID(audit_id), requirement_id=req_pending.id, applicability_status="applicable"))
        db.commit()

    # 3. Check readiness now: should be ready
    ready_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/threat-readiness",
        headers=headers,
    )
    assert ready_res.status_code == 200
    assert ready_res.json()["is_ready"] is True
    assert ready_res.json()["approved_requirements_count"] == 1
    assert ready_res.json()["pending_requirements_count"] == 1

    # 4. Prepare Mock Gemini Client with structured threat modeling response
    mock_llm = MockGeminiClient()
    mock_llm.queue_response({
        "assets": [
            {
                "name": "Customer Authentication Database",
                "asset_category": "data_store",
                "description": "Database storing credentials and hashed secrets.",
                "sensitivity": "confidential",
                "criticality": "critical",
                "data_classification": "PII & Credentials",
                "owner": "Auth Team",
                "relevant_component": "Database Cluster",
                "evidence_classification": "documented_fact",
                "confidence_score": 0.95,
                "source_references": [
                    {
                        "document_id": doc_id,
                        "original_filename": "payment_architecture.pdf",
                        "page_number": 1,
                        "section_title": "Section 1.1 Architecture Overview",
                        "exact_excerpt": "Customer Authentication Database",
                        "evidence_classification": "documented_fact",
                    }
                ],
            }
        ],
        "attack_surfaces": [
            {
                "name": "Public Auth API",
                "surface_type": "public_api",
                "description": "Public REST entrypoint at /api/v1/auth/login.",
                "exposed_component": "API Gateway",
                "access_requirements": "unauthenticated",
                "trust_boundary": "Internet-to-DMZ",
                "evidence_classification": "documented_fact",
                "confidence_score": 0.92,
                "associated_assets": ["Customer Authentication Database"],
                "source_references": [
                    {
                        "document_id": doc_id,
                        "original_filename": "payment_architecture.pdf",
                        "page_number": 1,
                        "section_title": "Section 1.1 Architecture Overview",
                        "exact_excerpt": "Public REST Auth API at /api/v1/auth/login",
                        "evidence_classification": "documented_fact",
                    }
                ],
            }
        ],
        "threats": [
            {
                "threat_title": "Credential Stuffing and Brute Force on Auth Gateway",
                "threat_description": "Attacker initiates automated credential stuffing attack against unauthenticated endpoint.",
                "stride_category": "Spoofing",
                "attack_objective": "Obtain valid JWT tokens and hijack customer sessions",
                "attack_vector": "Automated HTTP POST requests",
                "entry_point": "/api/v1/auth/login",
                "preconditions": "No rate limiting or captcha enforced on endpoint",
                "attack_steps": [
                    "1. Discover exposed public auth endpoint.",
                    "2. Transmit dictionary payload.",
                    "3. Extract valid access tokens.",
                ],
                "target_assets": ["Customer Authentication Database"],
                "affected_components": ["API Gateway"],
                "trust_boundaries_crossed": ["Internet -> DMZ"],
                "potential_consequences": "Customer account takeover and reputational damage",
                "cia_confidentiality": "high",
                "cia_integrity": "medium",
                "cia_availability": "low",
                "likelihood_score": 4,
                "likelihood_rationale": "High frequency of automated scanning on public endpoints.",
                "impact_score": 4,
                "impact_rationale": "Direct breach of customer accounts.",
                "is_provisional": False,
                "confidence_score": 0.90,
                "assumptions": ["Assumes no third party WAF or DDoS shield."],
                "missing_information": [],
                "attack_path": [
                    {
                        "node_id": "NODE-ROOT",
                        "parent_node_id": None,
                        "node_type": "root_objective",
                        "description": "Compromise customer accounts",
                        "logical_operator": "AND",
                        "sequence_number": 1,
                    },
                    {
                        "node_id": "NODE-EXPLOIT",
                        "parent_node_id": "NODE-ROOT",
                        "node_type": "exploit_action",
                        "description": "Send high-frequency credential pairs to login endpoint",
                        "logical_operator": None,
                        "sequence_number": 2,
                    },
                ],
                "source_references": [
                    {
                        "document_id": doc_id,
                        "original_filename": "payment_architecture.pdf",
                        "page_number": 1,
                        "section_title": "Section 1.1 Architecture Overview",
                        "exact_excerpt": "Public REST Auth API at /api/v1/auth/login",
                        "evidence_classification": "documented_fact",
                    }
                ],
                "mapped_requirements": [
                    {
                        "requirement_code": "REQ-PCI-3.4",
                        "relationship_type": "directly_related",
                        "rationale": "Exposes stored customer data protected by PCI-3.4.",
                        "confidence_score": 0.90,
                    },
                    {
                        "requirement_code": "REQ-PCI-8.3",  # Pending requirement! Must be ignored.
                        "relationship_type": "directly_related",
                        "rationale": "Relates to authentication controls.",
                        "confidence_score": 0.85,
                    },
                ],
            }
        ],
        "analysis_summary": "System analysis identified internet-exposed auth endpoint with potential for brute force.",
        "assumptions": ["Single region deployment."],
        "missing_information": [],
    })
    set_gemini_client(mock_llm)

    # 5. Trigger threat analysis run
    run_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/threat-analysis",
        headers=headers,
        json={"model_name": "gemini-1.5-flash", "run_in_background": False},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert run_data["assets_discovered_count"] == 1
    assert run_data["attack_surfaces_count"] == 1
    assert run_data["threats_generated_count"] == 1

    # 6. Verify discovered assets endpoint
    assets_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/assets",
        headers=headers,
    )
    assert assets_res.status_code == 200
    assets = assets_res.json()
    assert len(assets) == 1
    assert assets[0]["name"] == "Customer Authentication Database"
    assert assets[0]["asset_category"] == "data_store"
    assert assets[0]["criticality"] == "critical"
    assert assets[0]["evidence_classification"] == "documented_fact"

    # 7. Verify attack surfaces endpoint
    surfaces_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/attack-surfaces",
        headers=headers,
    )
    assert surfaces_res.status_code == 200
    surfaces = surfaces_res.json()
    assert len(surfaces) == 1
    assert surfaces[0]["name"] == "Public Auth API"
    assert surfaces[0]["trust_boundary"] == "Internet-to-DMZ"

    # 8. Verify threats list endpoint with STRIDE filter
    threats_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats?stride_category=Spoofing",
        headers=headers,
    )
    assert threats_res.status_code == 200
    threats_data = threats_res.json()
    assert threats_data["total_count"] == 1
    threat = threats_data["threats"][0]
    threat_id = threat["id"]
    assert threat["stride_category"] == "Spoofing"
    assert threat["likelihood_score"] == 4
    assert threat["impact_score"] == 4
    # Deterministic scoring: 4 * 4 = 16 => severity 'very_high'
    assert threat["risk_score"] == 16
    assert threat["severity"] == "very_high"
    assert threat["review_status"] == "pending_review"

    # 9. Verify threat detail endpoint (rich structure with attack path & requirement mappings)
    detail_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["attack_path_nodes"]) == 2
    assert detail["attack_path_nodes"][0]["node_id"] == "NODE-ROOT"
    assert detail["attack_path_nodes"][0]["logical_operator"] == "AND"

    # Requirement mapping test: ONLY approved REQ-PCI-3.4 must be mapped; pending REQ-PCI-8.3 excluded!
    mapped_reqs = detail["requirement_mappings"]
    assert len(mapped_reqs) == 1
    assert mapped_reqs[0]["requirement_code"] == "REQ-PCI-3.4"

    # Evidence references test: citation linked with verbatim check
    ev_refs = detail["evidence_references"]
    assert len(ev_refs) >= 1
    assert "Public REST Auth API" in ev_refs[0]["exact_excerpt"]
    assert ev_refs[0]["evidence_classification"] == "documented_fact"


# ============================================================================
# 4. Human Review Workflow Tests
# ============================================================================

def test_threat_human_review_workflow(client: TestClient):
    """Test accepting, rejecting with mandatory reason, editing, and audit history trail."""
    user = create_auth_user(client, "Review Org")
    headers = user["headers"]
    org_id = user["org_id"]
    audit_id = create_sample_audit(client, user)

    # Insert a test threat in database
    with SessionLocal() as db:
        threat = Threat(
            organization_id=uuid.UUID(org_id),
            audit_id=uuid.UUID(audit_id),
            threat_title="Unauthorized Database Dump via SQL Injection",
            threat_description="SQL injection in search parameter exposes database tables.",
            stride_category="Information Disclosure",
            threat_category="Information Disclosure",
            attack_vector="SQL Injection",
            entry_point="/api/v1/search",
            likelihood_score=2,
            impact_score=5,
            risk_score=10,
            severity="high",
            cia_confidentiality="critical",
            cia_integrity="high",
            cia_availability="low",
            review_status="pending_review",
        )
        db.add(threat)
        db.commit()
        db.refresh(threat)
        threat_id = str(threat.id)

    # 1. Reject without reason should fail with 400
    rej_fail = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}/reject",
        headers=headers,
        json={"action": "reject", "reason": ""},
    )
    assert rej_fail.status_code == 400

    # 2. Reject with reason
    rej_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}/reject",
        headers=headers,
        json={"action": "reject", "reason": "System uses parameterized ORM queries exclusively. No dynamic SQL."},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["review_status"] == "rejected"

    # 3. Request more information
    info_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}/request-review",
        headers=headers,
        json={"action": "request_review", "reason": "Need SAST report confirming ORM coverage."},
    )
    assert info_res.status_code == 200
    assert info_res.json()["review_status"] == "needs_more_information"

    # 4. Edit threat: modify likelihood & impact -> verify deterministic risk score recalculation
    edit_res = client.patch(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}",
        headers=headers,
        json={
            "likelihood_score": 5,
            "impact_score": 5,
            "threat_title": "Critical SQL Injection in Legacy Search",
            "reason": "Auditor verified vulnerability in legacy module.",
        },
    )
    assert edit_res.status_code == 200
    edited_data = edit_res.json()
    assert edited_data["review_status"] == "edited"
    assert edited_data["threat_title"] == "Critical SQL Injection in Legacy Search"
    assert edited_data["likelihood_score"] == 5
    assert edited_data["impact_score"] == 5
    # Recalculated: 5 * 5 = 25 => 'critical'
    assert edited_data["risk_score"] == 25
    assert edited_data["severity"] == "critical"

    # 5. Accept threat
    accept_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}/accept",
        headers=headers,
        json={"action": "accept", "reason": "Threat verified and acknowledged for remediation."},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["review_status"] == "accepted"

    # 6. Check immutable audit trail
    detail_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/threats/{threat_id}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    history = detail_res.json()["audit_history"]
    assert len(history) >= 4
    actions = [h["action"] for h in history]
    assert "reject" in actions
    assert "request_more_information" in actions
    assert "edit" in actions
    assert "accept" in actions


# ============================================================================
# 5. Multi-Tenant Isolation Tests
# ============================================================================

def test_cross_tenant_isolation_threats(client: TestClient):
    """Verify that User from Org B cannot view, trigger, or review threats in Org A."""
    user_a = create_auth_user(client, "Org A")
    user_b = create_auth_user(client, "Org B")

    audit_id_a = create_sample_audit(client, user_a)

    with SessionLocal() as db:
        threat_a = Threat(
            organization_id=uuid.UUID(user_a["org_id"]),
            audit_id=uuid.UUID(audit_id_a),
            threat_title="Org A Confidential Threat Scenario",
            threat_description="Restricted internal threat.",
            stride_category="Tampering",
            threat_category="Tampering",
            likelihood_score=3,
            impact_score=3,
            risk_score=9,
            severity="medium",
        )
        db.add(threat_a)
        db.commit()
        threat_id_a = str(threat_a.id)

    # User B attempts to access Org A's threats
    res = client.get(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_id_a}/threats",
        headers=user_b["headers"],
    )
    assert res.status_code == 404

    # User B attempts to get Org A's threat detail
    res_detail = client.get(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_id_a}/threats/{threat_id_a}",
        headers=user_b["headers"],
    )
    assert res_detail.status_code == 404

    # User B attempts to accept Org A's threat
    res_accept = client.post(
        f"/api/organizations/{user_a['org_id']}/audits/{audit_id_a}/threats/{threat_id_a}/accept",
        headers=user_b["headers"],
        json={"action": "accept"},
    )
    assert res_accept.status_code == 404
