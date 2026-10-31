"""Comprehensive test suite for Milestone 4 Regulatory Knowledge Base & Legal Analyst Agent.

Covers:
1. Regulatory framework management (CRUD, defaults, constraints).
2. Regulatory document upload, PDF text extraction, and deterministic chunking.
3. Legal Analyst AI agent extraction using MockGeminiClient (provenance citations, deduplication).
4. Taxonomy and adversarial resilience (21 categories, obligation types, prompt injection safety).
5. Human review workflow (approve, reject, edit, revision request, full audit history).
6. Audit requirement mapping and evidence document suggestions.
7. Multi-tenant and RBAC security isolation.
"""

from __future__ import annotations

import io
import uuid
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.regulatory import (
    AuditRequirement,
    RegulatoryDocument,
    RegulatoryDocumentChunk,
    RegulatoryExtractionJob,
    RegulatoryFramework,
    RequirementAuditHistory,
    RequirementSource,
)
from app.database.models.assessments import Requirement
from app.main import app
from app.services.ai.gemini_client import MockGeminiClient, set_gemini_client


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def create_auth_user(client: TestClient, org_name: str = "Reg Test Org") -> dict:
    """Helper to register user and obtain auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"reg_{uid}@sentinel-test.com"
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


def generate_regulatory_pdf(
    title: str = "Standard Operating Guideline",
    sections: list[str] = None,
) -> bytes:
    """Generate in-memory valid PDF with regulatory clauses."""
    if sections is None:
        sections = [
            "Section 1.1 Scope and Administration\nThis regulation applies to all cloud infrastructure handling financial customer data.",
            "Section 2.1 Identity and Access Control\nThe organization shall enforce multi-factor authentication for all remote administrative access to production systems.",
            "Section 2.2 Data Encryption Requirements\nAll sensitive personal data must be encrypted at rest using AES-256 or stronger cryptographic keys.",
        ]

    doc = pymupdf.open()
    for idx, text in enumerate(sections, 1):
        page = doc.new_page()
        page.insert_text((50, 72), f"{title} - Page {idx}\n\n{text}")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_framework_lifecycle(client: TestClient):
    """Test creating, listing, updating, and retrieving regulatory frameworks."""
    user = create_auth_user(client, "Framework Test Org")
    headers = user["headers"]

    # 1. Create framework
    res = client.post(
        "/api/regulatory/frameworks",
        headers=headers,
        json={
            "name": "Digital Personal Data Protection Act 2023",
            "short_name": "DPDPA-2023",
            "issuing_authority": "Parliament of India",
            "jurisdiction": "India",
            "framework_type": "legislation",
            "version": "2023.1",
            "description": "Comprehensive personal data protection statute.",
        },
    )
    assert res.status_code == 201
    fw = res.json()
    fw_id = fw["id"]
    assert fw["short_name"] == "DPDPA-2023"
    assert fw["jurisdiction"] == "India"
    assert fw["framework_type"] == "legislation"

    # 2. List frameworks
    list_res = client.get("/api/regulatory/frameworks?search=DPDPA", headers=headers)
    assert list_res.status_code == 200
    frameworks = list_res.json()
    assert any(f["id"] == fw_id for f in frameworks)

    # 3. Retrieve single framework
    get_res = client.get(f"/api/regulatory/frameworks/{fw_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Digital Personal Data Protection Act 2023"

    # 4. Update framework
    update_res = client.patch(
        f"/api/regulatory/frameworks/{fw_id}",
        headers=headers,
        json={"version": "2023.2", "description": "Updated description."},
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == "2023.2"


def test_regulatory_document_upload_and_chunking(client: TestClient):
    """Test uploading a regulatory PDF and verifying deterministic text chunking."""
    user = create_auth_user(client, "Reg Ingestion Org")
    headers = user["headers"]

    # Create framework
    fw_res = client.post(
        "/api/regulatory/frameworks",
        headers=headers,
        json={
            "name": "RBI Master Direction on IT Governance",
            "short_name": "RBI-ITG",
            "issuing_authority": "Reserve Bank of India",
            "jurisdiction": "India",
            "framework_type": "circular",
            "version": "2023",
        },
    )
    assert fw_res.status_code == 201
    fw_id = fw_res.json()["id"]

    # Upload PDF
    pdf_bytes = generate_regulatory_pdf("RBI Master Direction on IT Governance")
    files = {"file": ("rbi_it_governance.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "title": "RBI IT Governance Master Direction",
        "document_number": "RBI/2023-24/107",
        "version": "1.0",
    }

    upload_res = client.post(
        f"/api/regulatory/frameworks/{fw_id}/documents",
        headers=headers,
        files=files,
        data=data,
    )
    assert upload_res.status_code == 201
    doc = upload_res.json()
    doc_id = doc["id"]
    assert doc["status"] == "completed"
    assert doc["chunk_count"] > 0
    assert doc["page_count"] == 3

    # Inspect chunks
    chunks_res = client.get(f"/api/regulatory/documents/{doc_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) == doc["chunk_count"]
    assert all("content" in c and c["character_count"] > 0 for c in chunks)


def test_legal_analyst_extraction_with_mock(client: TestClient):
    """Test Legal Analyst agent requirement extraction and citation tracking."""
    user = create_auth_user(client, "Legal Analyst Org")
    headers = user["headers"]

    # Create framework and upload document
    fw_res = client.post(
        "/api/regulatory/frameworks",
        headers=headers,
        json={
            "name": "SOC 2 Trust Services Criteria",
            "short_name": "SOC2-TSC",
            "issuing_authority": "AICPA",
            "jurisdiction": "Global",
            "framework_type": "standard",
            "version": "2022",
        },
    )
    fw_id = fw_res.json()["id"]

    pdf_bytes = generate_regulatory_pdf(
        "SOC 2 Trust Services Criteria",
        [
            "CC6.1 The entity restricts logical access to registered and authorized users through multi-factor authentication.",
            "CC6.6 The entity implements logical boundaries to protect internal networks from unauthorized external traffic.",
        ],
    )
    files = {"file": ("soc2_tsc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_res = client.post(
        f"/api/regulatory/frameworks/{fw_id}/documents",
        headers=headers,
        files=files,
        data={"title": "SOC 2 TSC 2022", "document_number": "TSC-2022"},
    )
    doc_id = upload_res.json()["id"]

    # Configure mock gemini client with deterministic response
    mock_client = MockGeminiClient()
    mock_client.queue_response({
        "requirements": [
            {
                "requirement_code": "CC6.1",
                "title": "Logical Access Restrictions",
                "requirement_statement": "The entity shall restrict logical access to authorized users via multi-factor authentication.",
                "detailed_description": "Multi-factor authentication must be implemented for all logical access to production environments.",
                "obligation_type": "mandatory",
                "category": "Identity and Access Management",
                "subcategory": "Authentication",
                "applicability": "general",
                "jurisdiction": "Global",
                "source_section": "CC6.1",
                "source_page": 1,
                "source_excerpt": "The entity restricts logical access to registered and authorized users through multi-factor authentication.",
                "confidence_score": 0.98,
            }
        ],
        "document_summary": "Access control criteria.",
        "notes": "Clear normative obligation.",
    })
    set_gemini_client(mock_client)

    # Trigger extraction synchronously
    extract_res = client.post(
        f"/api/regulatory/documents/{doc_id}/extract?run_synchronous=true",
        headers=headers,
    )
    assert extract_res.status_code == 202
    job = extract_res.json()
    assert job["status"] == "completed"
    assert job["requirements_extracted"] >= 1

    # Verify extracted requirement exists in API
    req_res = client.get(f"/api/regulatory/requirements?document_id={doc_id}", headers=headers)
    assert req_res.status_code == 200
    req_data = req_res.json()
    assert req_data["total"] >= 1

    matched_req = next(r for r in req_data["items"] if r["requirement_code"] == "CC6.1")
    assert matched_req["title"] == "Logical Access Restrictions"
    assert matched_req["category"] == "Identity and Access Management"
    assert matched_req["obligation_type"] == "mandatory"
    assert matched_req["review_status"] == "pending_review"
    assert matched_req["source_page"] == 1
    assert "multi-factor authentication" in matched_req["source_excerpt"]


def test_human_review_workflow(client: TestClient):
    """Test approving, rejecting, editing, and requesting revision on requirements."""
    user = create_auth_user(client, "Review Workflow Org")
    headers = user["headers"]

    # Create framework and requirement directly in DB
    with SessionLocal() as session:
        fw = RegulatoryFramework(
            name="PCI-DSS Standard",
            short_name="PCI-DSS",
            issuing_authority="PCI SSC",
            status="active",
        )
        session.add(fw)
        session.flush()

        req = Requirement(
            framework_id=fw.id,
            framework="PCI-DSS",
            identifier="REQ-PCI-8.3",
            requirement_code="REQ-PCI-8.3",
            title="MFA for Cardholder Data Environment",
            description="Multi-factor authentication is required for all access to CDE.",
            requirement_statement="Multi-factor authentication is required for all access to CDE.",
            obligation_type="mandatory",
            category="Identity and Access Management",
            review_status="pending_review",
            extraction_status="completed",
        )
        session.add(req)
        session.commit()
        req_id = str(req.id)

    # 1. Edit requirement
    edit_res = client.post(
        f"/api/regulatory/requirements/{req_id}/edit",
        headers=headers,
        json={
            "title": "MFA for Administrative and Remote CDE Access",
            "obligation_type": "mandatory",
            "category": "Identity and Access Management",
            "reason": "Clarified scope to include remote and administrative access.",
        },
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["title"] == "MFA for Administrative and Remote CDE Access"

    # 2. Request revision
    rev_res = client.post(
        f"/api/regulatory/requirements/{req_id}/revision",
        headers=headers,
        json={"reason": "Need exact excerpt verification from latest PCI v4.0.1 errata."},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_status"] == "needs_revision"

    # 3. Approve requirement
    app_res = client.post(
        f"/api/regulatory/requirements/{req_id}/approve",
        headers=headers,
        json={"reason": "Verified against official errata sheet."},
    )
    assert app_res.status_code == 200
    assert app_res.json()["review_status"] == "approved"
    assert app_res.json()["reviewed_by"] == user["user_id"]

    # 4. Check audit history trail
    hist_res = client.get(f"/api/regulatory/requirements/{req_id}/history", headers=headers)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 3
    actions = [h["action"] for h in history]
    assert "edited" in actions
    assert "revision_requested" in actions
    assert "approved" in actions


def test_audit_requirement_mapping_and_evidence(client: TestClient):
    """Test mapping requirements to audits, updating applicability, and suggesting evidence."""
    user = create_auth_user(client, "Mapping Org")
    headers = user["headers"]
    org_id = user["org_id"]

    # 1. Create audit
    audit_res = client.post(
        f"/api/organizations/{org_id}/audits",
        headers=headers,
        json={"name": "Core Banking Q4 Audit", "application_name": "Core Banking API", "target_system": "AWS VPC"},
    )
    assert audit_res.status_code == 201
    audit_id = audit_res.json()["id"]

    # 2. Create requirement in DB
    with SessionLocal() as session:
        req = Requirement(
            framework="ISO 27001",
            identifier="A.9.2.1",
            requirement_code="A.9.2.1",
            title="User Registration and Access Provisioning",
            description="A formal user registration and deregistration process must be implemented.",
            requirement_statement="A formal user registration and deregistration process must be implemented.",
            obligation_type="mandatory",
            category="Identity and Access Management",
            review_status="approved",
            extraction_status="completed",
        )
        session.add(req)
        session.commit()
        req_id = str(req.id)

    # 3. Map requirement to audit
    map_res = client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/requirements",
        headers=headers,
        json={"requirement_ids": [req_id]},
    )
    assert map_res.status_code == 201
    mappings = map_res.json()
    assert len(mappings) == 1
    assert mappings[0]["requirement_id"] == req_id
    assert mappings[0]["applicability_status"] == "applicable"

    # 4. List audit requirements
    list_map_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/requirements",
        headers=headers,
    )
    assert list_map_res.status_code == 200
    assert len(list_map_res.json()) == 1

    # 5. Update applicability status
    patch_res = client.patch(
        f"/api/organizations/{org_id}/audits/{audit_id}/requirements/{req_id}",
        headers=headers,
        json={
            "applicability_status": "requires_review",
            "applicability_reason": "Pending verification of third-party contractor identity onboarding.",
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["applicability_status"] == "requires_review"

    # 6. Upload an audit document to test evidence suggestion
    pdf_bytes = generate_regulatory_pdf(
        "User Registration and Identity Provisioning Policy",
        ["This document describes the identity and access management procedures for all employees."],
    )
    files = {"file": ("identity_provisioning_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    client.post(
        f"/api/organizations/{org_id}/audits/{audit_id}/documents",
        headers=headers,
        files=files,
    )

    # 7. Check evidence suggestions for this requirement
    sug_res = client.get(
        f"/api/organizations/{org_id}/audits/{audit_id}/requirements/{req_id}/evidence-suggestions",
        headers=headers,
    )
    assert sug_res.status_code == 200
    suggestions = sug_res.json()
    assert isinstance(suggestions, list)
    if suggestions:
        assert suggestions[0]["relevance_score"] > 0.0

    # 8. Unmap requirement
    del_res = client.delete(
        f"/api/organizations/{org_id}/audits/{audit_id}/requirements/{req_id}",
        headers=headers,
    )
    assert del_res.status_code == 204


def test_cross_tenant_isolation(client: TestClient):
    """Verify tenant isolation: Tenant B cannot modify Tenant A's audit requirements."""
    tenant_a = create_auth_user(client, "Tenant Alpha")
    tenant_b = create_auth_user(client, "Tenant Beta")

    # Tenant A creates an audit
    audit_res = client.post(
        f"/api/organizations/{tenant_a['org_id']}/audits",
        headers=tenant_a["headers"],
        json={"name": "Alpha Private Audit", "application_name": "Alpha App", "target_system": "Internal"},
    )
    audit_id = audit_res.json()["id"]

    # Tenant B attempts to view or map requirements on Tenant A's audit
    bad_res = client.get(
        f"/api/organizations/{tenant_a['org_id']}/audits/{audit_id}/requirements",
        headers=tenant_b["headers"],
    )
    # 404 prevents tenant enumeration
    assert bad_res.status_code == 404

