import uuid
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.database.connection import check_db_health
from app.database.models import (
    Organization,
    User,
    OrganizationMember,
    Audit,
    AuditRun,
    AuditDocument,
    DocumentChunk,
    Requirement,
    Threat,
    ControlAssessment,
    Finding,
    EvidenceReference,
    FindingRequirement,
    FindingThreat,
    AgentRun,
    AgentEvent,
    AgentOutput,
    AdjudicationQuestion,
    AdjudicationAnswer,
    Report,
)


def test_1_database_connectivity(engine):
    """Test 1: Verify database connectivity against YugabyteDB."""
    health = check_db_health()
    assert health["status"] == "healthy"
    assert "Yugabyte" in health["version"] or "PostgreSQL" in health["version"]


def test_2_all_20_tables_exist(engine):
    """Test 2: Verify all 20 required tables were created through Alembic migrations."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "organizations",
        "users",
        "organization_members",
        "audits",
        "audit_runs",
        "audit_documents",
        "document_chunks",
        "requirements",
        "threats",
        "control_assessments",
        "findings",
        "evidence_references",
        "finding_requirements",
        "finding_threats",
        "agent_runs",
        "agent_events",
        "agent_outputs",
        "adjudication_questions",
        "adjudication_answers",
        "reports",
    }

    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_3_to_5_identity_and_tenancy(db_session):
    """Test 3, 4, 5: Organization, User, and Member creation with valid roles."""
    org = Organization(name="Acme Corp", slug=f"acme-{uuid.uuid4().hex[:8]}")
    user = User(
        email=f"ciso-{uuid.uuid4().hex[:8]}@acme.com",
        hashed_password="hashed_secret_pw",
        full_name="Elena Vance",
    )
    db_session.add_all([org, user])
    db_session.flush()

    assert org.id is not None
    assert user.id is not None

    # Valid role assignment
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db_session.add(member)
    db_session.flush()
    assert member.id is not None
    assert member.role == "owner"


def test_6_and_7_audit_and_multiple_runs(db_session):
    """Test 6 & 7: Audit creation and supporting multiple runs under one audit."""
    org = Organization(name="FinTech Corp", slug=f"fintech-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    audit = Audit(
        organization_id=org.id,
        title="Payment Core v2.4",
        target_system="Production VPC",
        environment="production",
    )
    db_session.add(audit)
    db_session.flush()

    # Create run 1
    run1 = AuditRun(
        organization_id=org.id,
        audit_id=audit.id,
        run_number=1,
        status="completed",
        risk_score=72.5,
    )
    db_session.add(run1)
    db_session.flush()

    # Create run 2 (preserving previous run)
    run2 = AuditRun(
        organization_id=org.id,
        audit_id=audit.id,
        run_number=2,
        status="running",
        risk_score=68.0,
    )
    db_session.add(run2)
    db_session.flush()

    assert run1.id != run2.id
    assert run1.run_number == 1
    assert run2.run_number == 2


def test_8_document_and_chunks(db_session):
    """Test 8: Document and chunk relationships without storing file binary in DB."""
    org = Organization(name="Doc Org", slug=f"doc-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    audit = Audit(organization_id=org.id, title="Doc Audit", target_system="S3 Gateway")
    db_session.add(audit)
    db_session.flush()

    run = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=1, status="running")
    db_session.add(run)
    db_session.flush()

    doc = AuditDocument(
        organization_id=org.id,
        audit_id=audit.id,
        audit_run_id=run.id,
        file_name="pci_dss_arch.pdf",
        file_size_bytes=1048576,
        mime_type="application/pdf",
        storage_path="s3://compliance-bucket/docs/pci_dss_arch.pdf",
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status="indexed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        organization_id=org.id,
        audit_run_id=run.id,
        audit_document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Primary account numbers (PAN) must be rendered unreadable anywhere they are stored.",
        start_char_offset=0,
        end_char_offset=85,
    )
    chunk2 = DocumentChunk(
        organization_id=org.id,
        audit_run_id=run.id,
        audit_document_id=doc.id,
        chunk_index=1,
        page_number=1,
        content="Cryptography using AES-256 with KMS HSM key management is deployed across VPC.",
        start_char_offset=86,
        end_char_offset=167,
    )
    db_session.add_all([chunk1, chunk2])
    db_session.flush()

    assert doc.id is not None
    assert len(doc.chunks) == 2


def test_9_to_13_compliance_findings_agents_reports(db_session):
    """Test 9-13: Requirements, Threats, Assessments, Findings, Evidence, Agents, Adjudication, Reports."""
    org = Organization(name="Compliance Org", slug=f"comp-{uuid.uuid4().hex[:8]}")
    user = User(email=f"auditor-{uuid.uuid4().hex[:8]}@audit.org", hashed_password="pw")
    db_session.add_all([org, user])
    db_session.flush()

    audit = Audit(organization_id=org.id, title="FinSec", target_system="Banking VPC")
    db_session.add(audit)
    db_session.flush()

    run = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=1, status="completed", risk_score=88.0)
    db_session.add(run)
    db_session.flush()

    # Document
    doc = AuditDocument(
        organization_id=org.id,
        audit_id=audit.id,
        audit_run_id=run.id,
        file_name="spec.pdf",
        file_size_bytes=50000,
        mime_type="application/pdf",
        storage_path="/storage/spec.pdf",
        checksum_sha256="abc1234567890123456789012345678901234567890123456789012345678901",
        status="indexed",
    )
    db_session.add(doc)
    db_session.flush()

    # 9. Requirement & Threat
    req = Requirement(
        organization_id=org.id,
        audit_run_id=run.id,
        framework="PCI-DSS",
        identifier="Req 3.4",
        title="Render PAN unreadable",
        description="Render PAN unreadable anywhere it is stored",
    )
    threat = Threat(
        organization_id=org.id,
        audit_run_id=run.id,
        threat_id_code="THR-001",
        title="Unencrypted S3 Exfiltration",
        description="Public bucket allows extraction of cardholder data",
        threat_category="Data Exfiltration",
        severity="critical",
    )
    db_session.add_all([req, threat])
    db_session.flush()

    assessment = ControlAssessment(
        organization_id=org.id,
        audit_run_id=run.id,
        requirement_id=req.id,
        threat_id=threat.id,
        status="partially_satisfied",
        rationale="KMS CMK enabled but key rotation policy unset",
        confidence_score=0.95,
    )
    db_session.add(assessment)
    db_session.flush()

    # 10. Finding & Evidence
    finding = Finding(
        organization_id=org.id,
        audit_run_id=run.id,
        finding_code="FIND-001",
        title="Key rotation disabled on S3 KMS bucket",
        description="AWS KMS key rotation is not enabled on production cardholder bucket.",
        severity="high",
        evidence_state="confirmed_weakness",
        cvss_score=7.5,
    )
    db_session.add(finding)
    db_session.flush()

    ev = EvidenceReference(
        organization_id=org.id,
        audit_run_id=run.id,
        finding_id=finding.id,
        document_id=doc.id,
        supporting_passage="Bucket policy references KMS key without auto_rotate attribute.",
        evidence_type="supports",
        page_number=3,
    )
    fr = FindingRequirement(
        organization_id=org.id,
        audit_run_id=run.id,
        finding_id=finding.id,
        requirement_id=req.id,
    )
    ft = FindingThreat(
        organization_id=org.id,
        audit_run_id=run.id,
        finding_id=finding.id,
        threat_id=threat.id,
    )
    db_session.add_all([ev, fr, ft])
    db_session.flush()

    # 11. Agent Run, Event, Output
    agent_run = AgentRun(
        organization_id=org.id,
        audit_run_id=run.id,
        agent_type="legal_analyst",
        status="completed",
        n8n_execution_id="exec-88910",
    )
    db_session.add(agent_run)
    db_session.flush()

    event = AgentEvent(
        organization_id=org.id,
        audit_run_id=run.id,
        agent_run_id=agent_run.id,
        event_type="rule_evaluated",
        message="PCI DSS 3.4 rule parsed",
        payload={"rule_id": "3.4"},
    )
    output = AgentOutput(
        organization_id=org.id,
        audit_run_id=run.id,
        agent_run_id=agent_run.id,
        output_type="compliance_evaluation",
        structured_data={"compliant": False, "score": 72},
        summary="Found 1 violation in storage bucket encryption",
    )
    db_session.add_all([event, output])
    db_session.flush()

    # 12. Adjudication Question & Answer
    question = AdjudicationQuestion(
        organization_id=org.id,
        audit_run_id=run.id,
        finding_id=finding.id,
        question_text="Does backup bucket use client-side or server-side encryption?",
        status="pending",
    )
    db_session.add(question)
    db_session.flush()

    answer = AdjudicationAnswer(
        organization_id=org.id,
        audit_run_id=run.id,
        question_id=question.id,
        user_id=user.id,
        answer_text="All backups use KMS client-side envelope encryption before storage.",
    )
    db_session.add(answer)
    db_session.flush()

    # 13. Report
    report = Report(
        organization_id=org.id,
        audit_id=audit.id,
        audit_run_id=run.id,
        title="Q3 2024 PCI-DSS Assessment Report",
        version=1,
        format="pdf",
        generation_status="completed",
        storage_path="/reports/2024/q3_pci_dss.pdf",
    )
    db_session.add(report)
    db_session.flush()

    assert report.id is not None
    assert report.generation_status == "completed"


def test_14_invalid_status_rejected(db_session):
    """Test 14: Check constraints reject invalid status values."""
    org = Organization(name="Check Org", slug=f"check-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    audit = Audit(organization_id=org.id, title="Test Audit", target_system="Sys")
    db_session.add(audit)
    db_session.flush()

    # Attempt invalid audit run status
    run = AuditRun(
        organization_id=org.id,
        audit_id=audit.id,
        run_number=1,
        status="invalid_unknown_status",
    )
    db_session.add(run)
    with pytest.raises((IntegrityError, DBAPIError)):
        db_session.flush()
    db_session.rollback()


def test_15_duplicate_membership_rejected(db_session):
    """Test 15: Unique constraint rejects duplicate organization membership."""
    org = Organization(name="Dup Org", slug=f"dup-{uuid.uuid4().hex[:8]}")
    user = User(email=f"user-{uuid.uuid4().hex[:8]}@dup.org", hashed_password="pw")
    db_session.add_all([org, user])
    db_session.flush()

    m1 = OrganizationMember(organization_id=org.id, user_id=user.id, role="analyst")
    db_session.add(m1)
    db_session.flush()

    # Duplicate membership
    m2 = OrganizationMember(organization_id=org.id, user_id=user.id, role="viewer")
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

