import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import (
    Organization,
    Audit,
    AuditRun,
    AuditDocument,
    Requirement,
    Finding,
    EvidenceReference,
    FindingRequirement,
)


def test_16_cross_tenant_references_rejected(db_session):
    """Test 16: Ensure cross-tenant composite FK references are strictly rejected."""
    # Organization A
    org_a = Organization(name="Tenant Alpha", slug=f"alpha-{uuid.uuid4().hex[:8]}")
    # Organization B
    org_b = Organization(name="Tenant Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    # Audit belongs to Tenant A
    audit_a = Audit(organization_id=org_a.id, title="Audit A", target_system="A VPC")
    db_session.add(audit_a)
    db_session.flush()

    # Attempt to create AuditRun with Tenant B's organization_id pointing to Tenant A's audit
    cross_tenant_run = AuditRun(
        organization_id=org_b.id,  # Tenant B
        audit_id=audit_a.id,       # But audit belongs to Tenant A!
        run_number=1,
        status="pending",
    )
    db_session.add(cross_tenant_run)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_17_cross_audit_run_references_rejected(db_session):
    """Test 17: Ensure relationships cannot connect findings and requirements from different audit runs."""
    org = Organization(name="Tenant Gamma", slug=f"gamma-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    audit = Audit(organization_id=org.id, title="Audit G", target_system="G VPC")
    db_session.add(audit)
    db_session.flush()

    # Create Run 1 and Run 2
    run1 = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=1, status="completed")
    run2 = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=2, status="running")
    db_session.add_all([run1, run2])
    db_session.flush()

    # Requirement belongs to Run 1
    req_run1 = Requirement(
        organization_id=org.id,
        audit_run_id=run1.id,
        framework="SOC2",
        identifier="CC6.1",
        title="Access Control",
        description="Logical access controls",
    )
    # Finding belongs to Run 2
    finding_run2 = Finding(
        organization_id=org.id,
        audit_run_id=run2.id,
        finding_code="FIND-RUN2",
        title="Unauthenticated access",
        description="Public API missing auth token validation",
        severity="high",
        evidence_state="confirmed_weakness",
    )
    db_session.add_all([req_run1, finding_run2])
    db_session.flush()

    # Attempt to link Finding from Run 2 to Requirement from Run 1 using Run 2's audit_run_id
    # Composite FK requires (organization_id, audit_run_id, requirement_id) to exist in requirements!
    cross_run_link = FindingRequirement(
        organization_id=org.id,
        audit_run_id=run2.id,  # Declaring it under Run 2
        finding_id=finding_run2.id,
        requirement_id=req_run1.id,  # But requirement belongs to Run 1!
    )
    db_session.add(cross_run_link)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_18_existing_audit_runs_remain_intact(db_session):
    """Test 18: Verify existing audit runs and findings remain completely intact when a new run is created."""
    org = Organization(name="Tenant Delta", slug=f"delta-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    audit = Audit(organization_id=org.id, title="Core Bank Audit", target_system="Banking Tier-0")
    db_session.add(audit)
    db_session.flush()

    # Run 1
    run1 = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=1, status="completed", risk_score=92.0)
    db_session.add(run1)
    db_session.flush()

    finding1 = Finding(
        organization_id=org.id,
        audit_run_id=run1.id,
        finding_code="FIND-001",
        title="Historical Weakness",
        description="Found in initial audit",
        severity="medium",
        evidence_state="confirmed_weakness",
    )
    db_session.add(finding1)
    db_session.flush()

    # Now create Run 2
    run2 = AuditRun(organization_id=org.id, audit_id=audit.id, run_number=2, status="running")
    db_session.add(run2)
    db_session.flush()

    # Verify Run 1 and finding1 are preserved and unaffected
    db_session.refresh(run1)
    assert run1.status == "completed"
    assert run1.risk_score == 92.0
    assert len(run1.findings) == 1
    assert run1.findings[0].id == finding1.id
    assert run2.run_number == 2

