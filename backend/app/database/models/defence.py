"""Database models for Defence Auditor: Control Discovery, Evidence Quality & Control Assessments (Milestone 6)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.assessments import ControlAssessment, Requirement, Threat
    from app.database.models.audits import Audit
    from app.database.models.documents import AuditDocument, DocumentChunk
    from app.database.models.findings import Finding
    from app.database.models.identity import Organization, User
    from app.database.models.threats import AttackPathNode, AttackSurface, DiscoveredAsset


class DefenceAnalysisRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An execution run of the Defence Auditor agent against an audit's evidence."""

    __tablename__ = "defence_analysis_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="gemini-1.5-flash", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)

    input_document_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    input_requirement_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    input_threat_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)

    controls_discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="defence_analysis_runs")
    discovered_controls: Mapped[List[DiscoveredControl]] = relationship(
        "DiscoveredControl",
        back_populates="defence_run",
        cascade="all, delete-orphan",
    )
    assessments: Mapped[List[ControlAssessment]] = relationship(
        "ControlAssessment",
        back_populates="defence_run",
    )
    findings: Mapped[List[Finding]] = relationship(
        "Finding",
        back_populates="defence_run",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_defence_run_status",
        ),
        Index("ix_defence_runs_org", "organization_id"),
        Index("ix_defence_runs_audit", "audit_id"),
        Index("ix_defence_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<DefenceAnalysisRun id={self.id} audit={self.audit_id} status={self.status}>"


class DiscoveredControl(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A security safeguard or control discovered from audit evidence documents."""

    __tablename__ = "discovered_controls"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    defence_analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("defence_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    control_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    control_objective: Mapped[str] = mapped_column(Text, nullable=False)

    implementation_status: Mapped[str] = mapped_column(
        String(50), default="documented", nullable=False
    )  # documented, partially_documented, undocumented, unknown
    operational_status: Mapped[str] = mapped_column(
        String(50), default="unverified", nullable=False
    )  # active, planned, unverified, unknown
    evidence_maturity: Mapped[str] = mapped_column(
        String(50), default="policy", nullable=False
    )  # policy, design, implementation, operational

    confidence_score: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), default=0.90, nullable=False
    )
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    control_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="discovered_controls")
    defence_run: Mapped[Optional[DefenceAnalysisRun]] = relationship(
        "DefenceAnalysisRun", back_populates="discovered_controls"
    )
    assessments: Mapped[List[ControlAssessment]] = relationship(
        "ControlAssessment",
        back_populates="control",
        cascade="all, delete-orphan",
    )
    requirement_mappings: Mapped[List[ControlRequirementMapping]] = relationship(
        "ControlRequirementMapping",
        back_populates="control",
        cascade="all, delete-orphan",
    )
    threat_mappings: Mapped[List[ControlThreatMapping]] = relationship(
        "ControlThreatMapping",
        back_populates="control",
        cascade="all, delete-orphan",
    )
    evidence_references: Mapped[List[ControlEvidenceReference]] = relationship(
        "ControlEvidenceReference",
        back_populates="control",
        cascade="all, delete-orphan",
    )
    audit_history: Mapped[List[ControlAuditHistory]] = relationship(
        "ControlAuditHistory",
        back_populates="control",
        cascade="all, delete-orphan",
        order_by="ControlAuditHistory.created_at.desc()",
    )
    finding_links: Mapped[List[FindingControl]] = relationship(
        "FindingControl",
        back_populates="control",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("audit_id", "control_code", name="uq_discovered_controls_audit_code"),
        CheckConstraint(
            "implementation_status IN ('documented', 'partially_documented', 'undocumented', 'unknown')",
            name="ck_ctrl_impl_status",
        ),
        CheckConstraint(
            "operational_status IN ('active', 'planned', 'unverified', 'unknown')",
            name="ck_ctrl_oper_status",
        ),
        CheckConstraint(
            "evidence_maturity IN ('policy', 'design', 'implementation', 'operational', 'unknown')",
            name="ck_ctrl_maturity",
        ),
        Index("ix_disc_ctrls_org", "organization_id"),
        Index("ix_disc_ctrls_audit", "audit_id"),
        Index("ix_disc_ctrls_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<DiscoveredControl id={self.id} code={self.control_code} name={self.name}>"


class ControlRequirementMapping(Base, UUIDPrimaryKeyMixin):
    """Mapping from a discovered security control to an approved regulatory requirement."""

    __tablename__ = "control_requirement_mappings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )

    coverage_level: Mapped[str] = mapped_column(
        String(50), default="supports", nullable=False
    )  # fully_covers, partially_covers, supports, potential_coverage
    mapping_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    confidence_score: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), default=0.90, nullable=False
    )
    review_status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    control: Mapped[DiscoveredControl] = relationship("DiscoveredControl", back_populates="requirement_mappings")
    requirement: Mapped[Requirement] = relationship("Requirement")

    __table_args__ = (
        UniqueConstraint("control_id", "requirement_id", name="uq_ctrl_req_map"),
        CheckConstraint(
            "coverage_level IN ('fully_covers', 'partially_covers', 'supports', 'potential_coverage')",
            name="ck_ctrl_req_coverage",
        ),
        Index("ix_ctrl_req_control", "control_id"),
        Index("ix_ctrl_req_req", "requirement_id"),
        Index("ix_ctrl_req_audit", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<ControlRequirementMapping control={self.control_id} req={self.requirement_id}>"


class ControlThreatMapping(Base, UUIDPrimaryKeyMixin):
    """Mapping from a discovered security control to an evaluated threat scenario."""

    __tablename__ = "control_threat_mappings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
    )

    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    attack_surface_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_surfaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    attack_path_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_path_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    mitigation_level: Mapped[str] = mapped_column(
        String(50), default="partially_mitigates", nullable=False
    )  # mitigates, partially_mitigates, detects, monitors, unverified
    mapping_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    confidence_score: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), default=0.90, nullable=False
    )
    review_status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    control: Mapped[DiscoveredControl] = relationship("DiscoveredControl", back_populates="threat_mappings")
    threat: Mapped[Threat] = relationship("Threat")
    asset: Mapped[Optional[DiscoveredAsset]] = relationship("DiscoveredAsset")
    attack_surface: Mapped[Optional[AttackSurface]] = relationship("AttackSurface")
    attack_path_node: Mapped[Optional[AttackPathNode]] = relationship("AttackPathNode")

    __table_args__ = (
        UniqueConstraint("control_id", "threat_id", name="uq_ctrl_threat_map"),
        CheckConstraint(
            "mitigation_level IN ('mitigates', 'partially_mitigates', 'detects', 'monitors', 'unverified')",
            name="ck_ctrl_threat_mitigation",
        ),
        Index("ix_ctrl_threat_control", "control_id"),
        Index("ix_ctrl_threat_threat", "threat_id"),
        Index("ix_ctrl_threat_audit", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<ControlThreatMapping control={self.control_id} threat={self.threat_id}>"


class ControlEvidenceReference(Base, UUIDPrimaryKeyMixin):
    """Verified evidence quotation linking a control or assessment to an audit document chunk."""

    __tablename__ = "control_evidence_references"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("control_assessments.id", ondelete="CASCADE"),
        nullable=True,
    )
    audit_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )

    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exact_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    citation_type: Mapped[str] = mapped_column(
        String(50), default="direct_evidence", nullable=False
    )  # direct_evidence, contradictory_evidence, contextual_evidence, inference, missing_evidence
    evidence_maturity: Mapped[str] = mapped_column(
        String(50), default="policy", nullable=False
    )  # policy, design, implementation, operational
    relevance_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    control: Mapped[DiscoveredControl] = relationship("DiscoveredControl", back_populates="evidence_references")
    document: Mapped[AuditDocument] = relationship("AuditDocument")
    chunk: Mapped[Optional[DocumentChunk]] = relationship("DocumentChunk")

    __table_args__ = (
        CheckConstraint(
            "citation_type IN ('direct_evidence', 'contradictory_evidence', 'contextual_evidence', 'inference', 'missing_evidence')",
            name="ck_ctrl_ev_citation_type",
        ),
        CheckConstraint(
            "evidence_maturity IN ('policy', 'design', 'implementation', 'operational')",
            name="ck_ctrl_ev_maturity",
        ),
        Index("ix_ctrl_ev_control", "control_id"),
        Index("ix_ctrl_ev_doc", "audit_document_id"),
        Index("ix_ctrl_ev_chunk", "document_chunk_id"),
        Index("ix_ctrl_ev_audit", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<ControlEvidenceReference control={self.control_id} type={self.citation_type}>"


class ControlAuditHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail for human review actions on controls and control assessments."""

    __tablename__ = "control_audit_history"

    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("control_assessments.id", ondelete="CASCADE"),
        nullable=True,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approve, reject, edit, request_more_information, reassess
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    changes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    control: Mapped[DiscoveredControl] = relationship("DiscoveredControl", back_populates="audit_history")
    reviewer: Mapped[Optional[User]] = relationship("User")

    __table_args__ = (
        Index("ix_ctrl_hist_control", "control_id"),
        Index("ix_ctrl_hist_reviewer", "reviewer_id"),
        Index("ix_ctrl_hist_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ControlAuditHistory control={self.control_id} action={self.action}>"


class FindingControl(Base, UUIDPrimaryKeyMixin):
    """Associates a finding or gap with one or more discovered controls."""

    __tablename__ = "finding_controls"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_controls.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="control_links")
    control: Mapped[DiscoveredControl] = relationship("DiscoveredControl", back_populates="finding_links")

    __table_args__ = (
        UniqueConstraint("finding_id", "control_id", name="uq_find_ctrl_finding_control"),
        Index("ix_find_ctrl_finding", "finding_id"),
        Index("ix_find_ctrl_control", "control_id"),
        Index("ix_find_ctrl_audit", "audit_id"),
    )

    def __repr__(self) -> str:
        return f"<FindingControl finding={self.finding_id} control={self.control_id}>"


class FindingAuditHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail for human review actions on findings."""

    __tablename__ = "finding_audit_history"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approve, reject, edit, request_more_information, reassess
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    changes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="audit_history")
    reviewer: Mapped[Optional[User]] = relationship("User")

    __table_args__ = (
        Index("ix_find_hist_finding", "finding_id"),
        Index("ix_find_hist_reviewer", "reviewer_id"),
        Index("ix_find_hist_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<FindingAuditHistory finding={self.finding_id} action={self.action}>"

