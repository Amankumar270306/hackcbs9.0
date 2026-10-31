from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
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
    from app.database.models.audits import AuditRun
    from app.database.models.identity import User
    from app.database.models.regulatory import (
        AuditRequirement,
        RegulatoryDocument,
        RegulatoryFramework,
        RequirementAuditHistory,
        RequirementSource,
    )


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "requirements"

    # Multi-tenant and audit run associations (nullable for canonical knowledge base requirements)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Framework linkages
    framework_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_frameworks.id", ondelete="SET NULL"),
        nullable=True,
    )
    regulatory_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Core identification & taxonomy
    framework: Mapped[str] = mapped_column(String(100), default="Custom", nullable=False)
    framework_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detailed_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Obligation and applicability
    obligation_type: Mapped[str] = mapped_column(String(50), default="mandatory", nullable=False)
    applicability: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    applicability_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Provenance citation fields
    source_section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # AI extraction & Human Review metadata
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    extraction_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    audit_run: Mapped[Optional[AuditRun]] = relationship("AuditRun", back_populates="requirements")
    regulatory_framework: Mapped[Optional[RegulatoryFramework]] = relationship(
        "RegulatoryFramework",
        back_populates="requirements",
    )
    regulatory_document: Mapped[Optional[RegulatoryDocument]] = relationship(
        "RegulatoryDocument",
        back_populates="requirements",
    )
    sources: Mapped[List[RequirementSource]] = relationship(
        "RequirementSource",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    audit_mappings: Mapped[List[AuditRequirement]] = relationship(
        "AuditRequirement",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    history: Mapped[List[RequirementAuditHistory]] = relationship(
        "RequirementAuditHistory",
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="RequirementAuditHistory.created_at.desc()",
    )
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewed_by])
    control_assessments: Mapped[List[ControlAssessment]] = relationship(
        "ControlAssessment",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Ensure synchronization between identifier and requirement_code
        if not self.identifier and self.requirement_code:
            self.identifier = self.requirement_code
        elif not self.requirement_code and self.identifier:
            self.requirement_code = self.identifier

        # Ensure synchronization between description and requirement_statement
        if not self.description and self.requirement_statement:
            self.description = self.requirement_statement
        elif not self.requirement_statement and self.description:
            self.requirement_statement = self.description

        if not self.detailed_description and self.description:
            self.detailed_description = self.description

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_requirements_org_run",
        ),
        UniqueConstraint("audit_run_id", "framework", "identifier", name="uq_req_run_framework_identifier"),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_req_org_run_id"),
        CheckConstraint(
            "obligation_type IN ('mandatory', 'conditional', 'recommended', 'informational', 'unclear')",
            name="ck_req_obligation_type",
        ),
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected', 'needs_revision')",
            name="ck_req_review_status",
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'extracting', 'completed', 'failed')",
            name="ck_req_extraction_status",
        ),
        Index("ix_requirements_org_id", "organization_id"),
        Index("ix_requirements_run_id", "audit_run_id"),
        Index("ix_requirements_framework", "framework"),
        Index("ix_requirements_framework_id", "framework_id"),
        Index("ix_requirements_doc_id", "regulatory_document_id"),
        Index("ix_requirements_review_status", "review_status"),
        Index("ix_requirements_code", "requirement_code"),
    )

    def __repr__(self) -> str:
        return f"<Requirement id={self.id} framework={self.framework} identifier={self.identifier}>"


class Threat(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "threats"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    threat_id_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    threat_category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    likelihood: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    audit_run: Mapped[AuditRun] = relationship("AuditRun", back_populates="threats")
    control_assessments: Mapped[List[ControlAssessment]] = relationship(
        "ControlAssessment",
        back_populates="threat",
        overlaps="requirement,control_assessments",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_threats_org_run",
        ),
        UniqueConstraint("audit_run_id", "threat_id_code", name="uq_threats_run_threat_code"),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_threats_org_run_id"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_threats_severity",
        ),
        CheckConstraint(
            "likelihood IS NULL OR likelihood IN ('low', 'medium', 'high')",
            name="ck_threats_likelihood",
        ),
        Index("ix_threats_org_id", "organization_id"),
        Index("ix_threats_run_id", "audit_run_id"),
        Index("ix_threats_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Threat id={self.id} code={self.threat_id_code} severity={self.severity}>"


class ControlAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "control_assessments"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    threat_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)

    # Relationships
    requirement: Mapped[Requirement] = relationship("Requirement", back_populates="control_assessments")
    threat: Mapped[Optional[Threat]] = relationship(
        "Threat",
        back_populates="control_assessments",
        overlaps="requirement,control_assessments",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "requirement_id"],
            ["requirements.organization_id", "requirements.audit_run_id", "requirements.id"],
            ondelete="CASCADE",
            name="fk_ctrl_assess_org_run_req",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "threat_id"],
            ["threats.organization_id", "threats.audit_run_id", "threats.id"],
            ondelete="RESTRICT",
            name="fk_ctrl_assess_org_run_threat",
        ),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_ctrl_assess_org_run_id"),
        CheckConstraint(
            "status IN ('satisfied', 'partially_satisfied', 'not_satisfied', 'not_documented', 'not_applicable', 'needs_review')",
            name="ck_ctrl_assess_status",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_ctrl_assess_confidence",
        ),
        Index("ix_ctrl_assess_org_id", "organization_id"),
        Index("ix_ctrl_assess_run_id", "audit_run_id"),
        Index("ix_ctrl_assess_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ControlAssessment id={self.id} req_id={self.requirement_id} status={self.status}>"
