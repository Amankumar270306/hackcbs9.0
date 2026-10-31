from __future__ import annotations

from datetime import datetime
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
    from app.database.models.identity import Organization, User
    from app.database.models.documents import AuditDocument
    from app.database.models.assessments import Requirement, Threat, ControlAssessment
    from app.database.models.findings import Finding
    from app.database.models.agents import AgentRun
    from app.database.models.reports import Report
    from app.database.models.regulatory import AuditRequirement
    from app.database.models.threats import (
        AttackSurface,
        DiscoveredAsset,
        ThreatAnalysisRun,
    )
    from app.database.models.defence import (
        DefenceAnalysisRun,
        DiscoveredControl,
    )
    from app.database.models.adjudication import (
        AdjudicationRun,
        AdjudicationDecision,
        AdjudicationContradiction,
    )


class Audit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audits"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    application_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_system: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(100), default="production", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="audits")
    creator: Mapped[Optional[User]] = relationship("User")
    runs: Mapped[List[AuditRun]] = relationship(
        "AuditRun",
        back_populates="audit",
        cascade="all, delete-orphan",
        order_by="AuditRun.run_number.desc()",
    )
    documents: Mapped[List[AuditDocument]] = relationship(
        "AuditDocument",
        back_populates="audit",
        primaryjoin="Audit.id == AuditDocument.audit_id",
        foreign_keys="[AuditDocument.audit_id]",
        cascade="all, delete-orphan",
        order_by="AuditDocument.created_at.desc()",
    )
    audit_requirements: Mapped[List[AuditRequirement]] = relationship(
        "AuditRequirement",
        back_populates="audit",
        primaryjoin="Audit.id == AuditRequirement.audit_id",
        foreign_keys="[AuditRequirement.audit_id]",
        cascade="all, delete-orphan",
        order_by="AuditRequirement.created_at.desc()",
    )
    threat_analysis_runs: Mapped[List[ThreatAnalysisRun]] = relationship(
        "ThreatAnalysisRun",
        back_populates="audit",
        primaryjoin="Audit.id == ThreatAnalysisRun.audit_id",
        foreign_keys="[ThreatAnalysisRun.audit_id]",
        cascade="all, delete-orphan",
        order_by="ThreatAnalysisRun.created_at.desc()",
    )
    discovered_assets: Mapped[List[DiscoveredAsset]] = relationship(
        "DiscoveredAsset",
        primaryjoin="Audit.id == DiscoveredAsset.audit_id",
        foreign_keys="[DiscoveredAsset.audit_id]",
        cascade="all, delete-orphan",
        order_by="DiscoveredAsset.created_at.desc()",
    )
    attack_surfaces: Mapped[List[AttackSurface]] = relationship(
        "AttackSurface",
        primaryjoin="Audit.id == AttackSurface.audit_id",
        foreign_keys="[AttackSurface.audit_id]",
        cascade="all, delete-orphan",
        order_by="AttackSurface.created_at.desc()",
    )
    threats: Mapped[List[Threat]] = relationship(
        "Threat",
        back_populates="audit",
        primaryjoin="Audit.id == Threat.audit_id",
        foreign_keys="[Threat.audit_id]",
        cascade="all, delete-orphan",
        order_by="Threat.created_at.desc()",
    )
    defence_analysis_runs: Mapped[List[DefenceAnalysisRun]] = relationship(
        "DefenceAnalysisRun",
        back_populates="audit",
        primaryjoin="Audit.id == DefenceAnalysisRun.audit_id",
        foreign_keys="[DefenceAnalysisRun.audit_id]",
        cascade="all, delete-orphan",
        order_by="DefenceAnalysisRun.created_at.desc()",
    )
    discovered_controls: Mapped[List[DiscoveredControl]] = relationship(
        "DiscoveredControl",
        back_populates="audit",
        primaryjoin="Audit.id == DiscoveredControl.audit_id",
        foreign_keys="[DiscoveredControl.audit_id]",
        cascade="all, delete-orphan",
        order_by="DiscoveredControl.created_at.desc()",
    )
    control_assessments: Mapped[List[ControlAssessment]] = relationship(
        "ControlAssessment",
        back_populates="audit",
        primaryjoin="Audit.id == ControlAssessment.audit_id",
        foreign_keys="[ControlAssessment.audit_id]",
        cascade="all, delete-orphan",
        order_by="ControlAssessment.created_at.desc()",
    )
    findings: Mapped[List[Finding]] = relationship(
        "Finding",
        back_populates="audit",
        primaryjoin="Audit.id == Finding.audit_id",
        foreign_keys="[Finding.audit_id]",
        cascade="all, delete-orphan",
        order_by="Finding.created_at.desc()",
    )
    adjudication_runs: Mapped[List[AdjudicationRun]] = relationship(
        "AdjudicationRun",
        back_populates="audit",
        primaryjoin="Audit.id == AdjudicationRun.audit_id",
        foreign_keys="[AdjudicationRun.audit_id]",
        cascade="all, delete-orphan",
        order_by="AdjudicationRun.created_at.desc()",
    )
    adjudication_decisions: Mapped[List[AdjudicationDecision]] = relationship(
        "AdjudicationDecision",
        back_populates="audit",
        primaryjoin="Audit.id == AdjudicationDecision.audit_id",
        foreign_keys="[AdjudicationDecision.audit_id]",
        cascade="all, delete-orphan",
        order_by="AdjudicationDecision.created_at.desc()",
    )
    adjudication_contradictions: Mapped[List[AdjudicationContradiction]] = relationship(
        "AdjudicationContradiction",
        back_populates="audit",
        primaryjoin="Audit.id == AdjudicationContradiction.audit_id",
        foreign_keys="[AdjudicationContradiction.audit_id]",
        cascade="all, delete-orphan",
        order_by="AdjudicationContradiction.created_at.desc()",
    )
    reports: Mapped[List[Report]] = relationship(
        "Report",
        back_populates="audit",
        primaryjoin="Audit.id == Report.audit_id",
        foreign_keys="[Report.audit_id]",
        cascade="all, delete-orphan",
        order_by="Report.version.desc()",
        overlaps="reports,audit_run",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_audits_org_id"),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived', 'completed')",
            name="ck_audits_status",
        ),
        Index("ix_audits_organization_id", "organization_id"),
        Index("ix_audits_target_system", "target_system"),
        Index("ix_audits_status", "status"),
        Index("ix_audits_created_by", "created_by"),
    )

    def __init__(self, **kwargs: Any) -> None:
        # Seamlessly synchronize name <-> title and application_name <-> target_system
        if "name" in kwargs and "title" not in kwargs:
            kwargs["title"] = kwargs["name"]
        elif "title" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs["title"]

        if "application_name" in kwargs and "target_system" not in kwargs:
            kwargs["target_system"] = kwargs["application_name"]
        elif "target_system" in kwargs and "application_name" not in kwargs:
            kwargs["application_name"] = kwargs["target_system"]

        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Audit id={self.id} org_id={self.organization_id} title={self.title} status={self.status}>"


class AuditRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    risk_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    audit: Mapped[Audit] = relationship("Audit", back_populates="runs")
    creator: Mapped[Optional[User]] = relationship("User")
    documents: Mapped[List[AuditDocument]] = relationship(
        "AuditDocument",
        back_populates="audit_run",
        primaryjoin="AuditRun.id == AuditDocument.audit_run_id",
        foreign_keys="[AuditDocument.audit_run_id]",
        cascade="all, delete-orphan",
    )
    requirements: Mapped[List[Requirement]] = relationship(
        "Requirement",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    threats: Mapped[List[Threat]] = relationship(
        "Threat",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    findings: Mapped[List[Finding]] = relationship(
        "Finding",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[List[AgentRun]] = relationship(
        "AgentRun",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    reports: Mapped[List[Report]] = relationship(
        "Report",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            ondelete="CASCADE",
            name="fk_audit_runs_org_audit",
        ),
        UniqueConstraint("audit_id", "run_number", name="uq_audit_runs_audit_run_number"),
        UniqueConstraint("organization_id", "id", name="uq_audit_runs_org_id"),
        UniqueConstraint("organization_id", "audit_id", "id", name="uq_audit_runs_org_audit_id"),
        CheckConstraint(
            "status IN ('queued', 'pending', 'running', 'completed', 'failed', 'in_review', 'cancelled')",
            name="ck_audit_run_status",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0.0 AND risk_score <= 100.0)",
            name="ck_audit_run_risk_score",
        ),
        Index("ix_audit_runs_org_id", "organization_id"),
        Index("ix_audit_runs_audit_id", "audit_id"),
        Index("ix_audit_runs_status", "status"),
        Index("ix_audit_runs_created_at", "created_at"),
        Index("ix_audit_runs_created_by", "created_by"),
    )

    def __init__(self, **kwargs: Any) -> None:
        if "config" not in kwargs or kwargs["config"] is None:
            kwargs["config"] = {}
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<AuditRun id={self.id} audit_id={self.audit_id} run_number={self.run_number} status={self.status}>"
