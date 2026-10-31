from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.audits import Audit, AuditRun
    from app.database.models.identity import User
    from app.database.models.assessments import Requirement, Threat
    from app.database.models.documents import AuditDocument, DocumentChunk
    from app.database.models.defence import (
        DefenceAnalysisRun,
        FindingControl,
        FindingAuditHistory,
    )


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "findings"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=True,
    )
    defence_analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("defence_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    finding_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_state: Mapped[str] = mapped_column(String(50), nullable=False)
    finding_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    likelihood_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impact_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)

    remediation_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation_recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cvss_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 1, asdecimal=False), nullable=True)

    review_status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finding_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    audit: Mapped[Optional[Audit]] = relationship("Audit", back_populates="findings")
    audit_run: Mapped[Optional[AuditRun]] = relationship("AuditRun", back_populates="findings")
    defence_run: Mapped[Optional[DefenceAnalysisRun]] = relationship("DefenceAnalysisRun", back_populates="findings")
    control_links: Mapped[List[FindingControl]] = relationship(
        "FindingControl",
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    audit_history: Mapped[List[FindingAuditHistory]] = relationship(
        "FindingAuditHistory",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="FindingAuditHistory.created_at.desc()",
    )
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewed_by])
    evidence_references: Mapped[List[EvidenceReference]] = relationship(
        "EvidenceReference",
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    finding_requirements: Mapped[List[FindingRequirement]] = relationship(
        "FindingRequirement",
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    finding_threats: Mapped[List[FindingThreat]] = relationship(
        "FindingThreat",
        back_populates="finding",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs: Any) -> None:
        if "remediation_recommendation" in kwargs and "remediation_guidance" not in kwargs:
            kwargs["remediation_guidance"] = kwargs["remediation_recommendation"]
        elif "remediation_guidance" in kwargs and "remediation_recommendation" not in kwargs:
            kwargs["remediation_recommendation"] = kwargs["remediation_guidance"]

        l_score = kwargs.get("likelihood_score")
        i_score = kwargs.get("impact_score")
        if l_score and i_score and "risk_score" not in kwargs:
            kwargs["risk_score"] = int(l_score) * int(i_score)

        if "risk_score" in kwargs and not kwargs.get("severity"):
            score = kwargs["risk_score"]
            if score >= 20:
                kwargs["severity"] = "critical"
            elif score >= 15:
                kwargs["severity"] = "very_high"
            elif score >= 10:
                kwargs["severity"] = "high"
            elif score >= 5:
                kwargs["severity"] = "medium"
            else:
                kwargs["severity"] = "low"

        super().__init__(**kwargs)

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_findings_org_run",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'very_high', 'critical')",
            name="ck_findings_severity",
        ),
        CheckConstraint(
            "evidence_state IN ('confirmed_weakness', 'insufficient_evidence', 'contradictory_evidence', 'awaiting_adjudication')",
            name="ck_findings_evidence_state",
        ),
        CheckConstraint(
            "finding_category IS NULL OR finding_category IN ('documentation_gap', 'implementation_evidence_gap', 'operational_evidence_gap', 'control_weakness', 'contradictory_evidence', 'coverage_gap')",
            name="ck_findings_category",
        ),
        CheckConstraint(
            "likelihood_score IS NULL OR (likelihood_score >= 1 AND likelihood_score <= 5)",
            name="ck_findings_likelihood",
        ),
        CheckConstraint(
            "impact_score IS NULL OR (impact_score >= 1 AND impact_score <= 5)",
            name="ck_findings_impact",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 1 AND risk_score <= 25)",
            name="ck_findings_risk_score",
        ),
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected', 'edited', 'needs_more_information')",
            name="ck_findings_review_status",
        ),
        CheckConstraint(
            "cvss_score IS NULL OR (cvss_score >= 0.0 AND cvss_score <= 10.0)",
            name="ck_findings_cvss_score",
        ),
        Index("ix_findings_org_id", "organization_id"),
        Index("ix_findings_audit_id", "audit_id"),
        Index("ix_findings_run_id", "audit_run_id"),
        Index("ix_findings_defence_run", "defence_analysis_run_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_evidence_state", "evidence_state"),
        Index("ix_findings_category", "finding_category"),
        Index("ix_findings_review_status", "review_status"),
    )

    def __repr__(self) -> str:
        return f"<Finding id={self.id} code={self.finding_code} severity={self.severity}>"


class EvidenceReference(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence_references"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    supporting_passage: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="evidence_references")
    document: Mapped[AuditDocument] = relationship("AuditDocument", overlaps="evidence_references,finding")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "finding_id"],
            ["findings.organization_id", "findings.audit_run_id", "findings.id"],
            ondelete="CASCADE",
            name="fk_evidence_refs_org_run_finding",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "document_id"],
            ["audit_documents.organization_id", "audit_documents.audit_run_id", "audit_documents.id"],
            ondelete="CASCADE",
            name="fk_evidence_refs_org_run_doc",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "chunk_id"],
            ["document_chunks.organization_id", "document_chunks.audit_run_id", "document_chunks.id"],
            ondelete="CASCADE",
            name="fk_evidence_refs_org_run_chunk",
        ),
        CheckConstraint(
            "evidence_type IN ('supports', 'contradicts', 'context')",
            name="ck_evidence_refs_type",
        ),
        Index("ix_evidence_refs_org_id", "organization_id"),
        Index("ix_evidence_refs_run_id", "audit_run_id"),
        Index("ix_evidence_refs_finding_id", "finding_id"),
        Index("ix_evidence_refs_doc_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<EvidenceReference id={self.id} finding_id={self.finding_id} type={self.evidence_type}>"


class FindingRequirement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "finding_requirements"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="finding_requirements")
    requirement: Mapped[Requirement] = relationship("Requirement", overlaps="finding,finding_requirements")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "finding_id"],
            ["findings.organization_id", "findings.audit_run_id", "findings.id"],
            ondelete="CASCADE",
            name="fk_find_req_org_run_finding",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "requirement_id"],
            ["requirements.organization_id", "requirements.audit_run_id", "requirements.id"],
            ondelete="CASCADE",
            name="fk_find_req_org_run_req",
        ),
        UniqueConstraint("finding_id", "requirement_id", name="uq_find_req_finding_requirement"),
        Index("ix_find_req_org_id", "organization_id"),
        Index("ix_find_req_run_id", "audit_run_id"),
        Index("ix_find_req_finding_id", "finding_id"),
        Index("ix_find_req_req_id", "requirement_id"),
    )

    def __repr__(self) -> str:
        return f"<FindingRequirement finding_id={self.finding_id} req_id={self.requirement_id}>"


class FindingThreat(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "finding_threats"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    threat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="finding_threats")
    threat: Mapped[Threat] = relationship("Threat", overlaps="finding,finding_threats")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "finding_id"],
            ["findings.organization_id", "findings.audit_run_id", "findings.id"],
            ondelete="CASCADE",
            name="fk_find_threat_org_run_finding",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "threat_id"],
            ["threats.organization_id", "threats.audit_run_id", "threats.id"],
            ondelete="CASCADE",
            name="fk_find_threat_org_run_threat",
        ),
        UniqueConstraint("finding_id", "threat_id", name="uq_find_threat_finding_threat"),
        Index("ix_find_threat_org_id", "organization_id"),
        Index("ix_find_threat_run_id", "audit_run_id"),
        Index("ix_find_threat_finding_id", "finding_id"),
        Index("ix_find_threat_threat_id", "threat_id"),
    )

    def __repr__(self) -> str:
        return f"<FindingThreat finding_id={self.finding_id} threat_id={self.threat_id}>"
