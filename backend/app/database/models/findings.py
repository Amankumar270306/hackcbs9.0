from datetime import datetime, timezone
import uuid
from typing import List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "findings"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    finding_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_state: Mapped[str] = mapped_column(String(50), nullable=False)
    remediation_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cvss_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)

    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="findings")
    evidence_references: Mapped[List["EvidenceReference"]] = relationship(
        "EvidenceReference",
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    finding_requirements: Mapped[List["FindingRequirement"]] = relationship(
        "FindingRequirement",
        back_populates="finding",
        cascade="all, delete-orphan",
    )
    finding_threats: Mapped[List["FindingThreat"]] = relationship(
        "FindingThreat",
        back_populates="finding",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_findings_org_run",
        ),
        UniqueConstraint("audit_run_id", "finding_code", name="uq_findings_run_finding_code"),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_findings_org_run_id"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_findings_severity",
        ),
        CheckConstraint(
            "evidence_state IN ('confirmed_weakness', 'insufficient_evidence', 'contradictory_evidence', 'awaiting_adjudication')",
            name="ck_findings_evidence_state",
        ),
        CheckConstraint(
            "cvss_score IS NULL OR (cvss_score >= 0.0 AND cvss_score <= 10.0)",
            name="ck_findings_cvss_score",
        ),
        Index("ix_findings_org_id", "organization_id"),
        Index("ix_findings_run_id", "audit_run_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_evidence_state", "evidence_state"),
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
    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence_references")
    document: Mapped["AuditDocument"] = relationship("AuditDocument", overlaps="evidence_references,finding")

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
    finding: Mapped["Finding"] = relationship("Finding", back_populates="finding_requirements")
    requirement: Mapped["Requirement"] = relationship("Requirement", overlaps="finding,finding_requirements")

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
    finding: Mapped["Finding"] = relationship("Finding", back_populates="finding_threats")
    threat: Mapped["Threat"] = relationship("Threat", overlaps="finding,finding_threats")

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
