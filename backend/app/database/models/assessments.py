import uuid
from typing import List, Optional
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "requirements"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    framework: Mapped[str] = mapped_column(String(100), nullable=False)
    framework_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="requirements")
    control_assessments: Mapped[List["ControlAssessment"]] = relationship(
        "ControlAssessment",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_requirements_org_run",
        ),
        UniqueConstraint("audit_run_id", "framework", "identifier", name="uq_req_run_framework_identifier"),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_req_org_run_id"),
        Index("ix_requirements_org_id", "organization_id"),
        Index("ix_requirements_run_id", "audit_run_id"),
        Index("ix_requirements_framework", "framework"),
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
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="threats")
    control_assessments: Mapped[List["ControlAssessment"]] = relationship(
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
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    # Relationships
    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="control_assessments")
    threat: Mapped[Optional["Threat"]] = relationship(
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
