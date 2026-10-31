"""Adversarial Strategist threat modeling database models for Compliance Sentinel.

Defines schemas for:
- ThreatAnalysisRun: Persistent threat-analysis execution tracking per audit.
- DiscoveredAsset: Discovered sensitive assets, data classifications, and criticality.
- AttackSurface: Exposed interfaces, trust boundaries, and access requirements.
- AttackPathNode: Structured attack-path tree nodes with AND/OR logical operators.
- ThreatAsset: Association mapping threats to affected assets.
- ThreatRequirementMapping: Association mapping threats to approved regulatory requirements.
- ThreatAuditHistory: Traceable audit trail of human review actions, edits, and decisions.
- ThreatEvidenceReference: Source citations linking threats to audit documents and chunks.
"""

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
    from app.database.models.identity import Organization, User
    from app.database.models.audits import Audit
    from app.database.models.assessments import Requirement, Threat
    from app.database.models.documents import AuditDocument, DocumentChunk


class ThreatAnalysisRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "threat_analysis_runs"

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
    model_name: Mapped[str] = mapped_column(String(100), default="gemini-3.5-flash-lite", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    input_document_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    input_requirement_ids: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    assets_discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attack_surfaces_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    threats_generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="threat_analysis_runs")
    assets: Mapped[List[DiscoveredAsset]] = relationship(
        "DiscoveredAsset",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    attack_surfaces: Mapped[List[AttackSurface]] = relationship(
        "AttackSurface",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    threats: Mapped[List[Threat]] = relationship(
        "Threat",
        back_populates="analysis_run",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'needs_review')",
            name="ck_threat_run_status",
        ),
        Index("ix_threat_runs_org", "organization_id"),
        Index("ix_threat_runs_audit", "audit_id"),
        Index("ix_threat_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ThreatAnalysisRun id={self.id} audit={self.audit_id} status={self.status}>"


class DiscoveredAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovered_assets"

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
    threat_analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threat_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    criticality: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    data_classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), default="Unknown", nullable=False)
    relevant_component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    evidence_classification: Mapped[str] = mapped_column(String(50), default="documented_fact", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), default=0.90, nullable=False)
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    asset_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    analysis_run: Mapped[Optional[ThreatAnalysisRun]] = relationship("ThreatAnalysisRun", back_populates="assets")
    threat_associations: Mapped[List[ThreatAsset]] = relationship(
        "ThreatAsset",
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "sensitivity IN ('public', 'internal', 'confidential', 'restricted', 'unknown')",
            name="ck_asset_sensitivity",
        ),
        CheckConstraint(
            "criticality IN ('low', 'medium', 'high', 'critical', 'unknown')",
            name="ck_asset_criticality",
        ),
        CheckConstraint(
            "evidence_classification IN ('documented_fact', 'inference', 'unknown', 'contradictory_information')",
            name="ck_asset_evidence_class",
        ),
        Index("ix_disc_assets_org", "organization_id"),
        Index("ix_disc_assets_audit", "audit_id"),
        Index("ix_disc_assets_category", "asset_category"),
    )

    def __repr__(self) -> str:
        return f"<DiscoveredAsset id={self.id} name={self.name} category={self.asset_category}>"


class AttackSurface(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attack_surfaces"

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
    threat_analysis_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threat_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    surface_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    exposed_component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_requirements: Mapped[str] = mapped_column(String(255), default="unknown", nullable=False)
    trust_boundary: Mapped[str] = mapped_column(String(255), default="unknown", nullable=False)
    evidence_classification: Mapped[str] = mapped_column(String(50), default="documented_fact", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), default=0.90, nullable=False)
    associated_assets: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    surface_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    analysis_run: Mapped[Optional[ThreatAnalysisRun]] = relationship("ThreatAnalysisRun", back_populates="attack_surfaces")

    __table_args__ = (
        CheckConstraint(
            "evidence_classification IN ('documented_fact', 'inference', 'unknown', 'contradictory_information')",
            name="ck_surface_evidence_class",
        ),
        Index("ix_attack_surfaces_org", "organization_id"),
        Index("ix_attack_surfaces_audit", "audit_id"),
        Index("ix_attack_surfaces_type", "surface_type"),
    )

    def __repr__(self) -> str:
        return f"<AttackSurface id={self.id} name={self.name} type={self.surface_type}>"


class AttackPathNode(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "attack_path_nodes"

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
    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
    )

    node_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "N1", "N1.1"
    parent_node_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    node_type: Mapped[str] = mapped_column(String(50), default="attack_step", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    logical_operator: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 'AND', 'OR', null
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supporting_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    threat: Mapped[Threat] = relationship("Threat", back_populates="attack_paths")

    __table_args__ = (
        CheckConstraint(
            "node_type IN ('root_objective', 'attack_step', 'precondition', 'exploit_action')",
            name="ck_attack_node_type",
        ),
        CheckConstraint(
            "logical_operator IS NULL OR logical_operator IN ('AND', 'OR')",
            name="ck_attack_node_operator",
        ),
        Index("ix_attack_nodes_threat", "threat_id"),
        Index("ix_attack_nodes_seq", "threat_id", "sequence_number"),
    )

    def __repr__(self) -> str:
        return f"<AttackPathNode id={self.id} threat={self.threat_id} node_id={self.node_id}>"


class ThreatAsset(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "threat_assets"

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
    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_assets.id", ondelete="CASCADE"),
        nullable=False,
    )

    relationship_type: Mapped[str] = mapped_column(String(50), default="target_asset", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    threat: Mapped[Threat] = relationship("Threat", back_populates="asset_mappings")
    asset: Mapped[DiscoveredAsset] = relationship("DiscoveredAsset", back_populates="threat_associations")

    __table_args__ = (
        UniqueConstraint("threat_id", "asset_id", name="uq_threat_assets_threat_asset"),
        CheckConstraint(
            "relationship_type IN ('target_asset', 'compromised_transit', 'secondary_impact')",
            name="ck_threat_asset_rel_type",
        ),
        Index("ix_threat_assets_threat", "threat_id"),
        Index("ix_threat_assets_asset", "asset_id"),
    )

    def __repr__(self) -> str:
        return f"<ThreatAsset threat={self.threat_id} asset={self.asset_id} rel={self.relationship_type}>"


class ThreatRequirementMapping(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "threat_requirement_mappings"

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
    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )

    relationship_type: Mapped[str] = mapped_column(String(50), default="directly_related", nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), default=0.90, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    threat: Mapped[Threat] = relationship("Threat", back_populates="requirement_mappings")
    requirement: Mapped[Requirement] = relationship("Requirement")

    __table_args__ = (
        UniqueConstraint("threat_id", "requirement_id", name="uq_threat_req_map"),
        CheckConstraint(
            "relationship_type IN ('directly_related', 'indirectly_related', 'potential_coverage', 'requires_review')",
            name="ck_threat_req_rel_type",
        ),
        Index("ix_threat_req_threat", "threat_id"),
        Index("ix_threat_req_requirement", "requirement_id"),
    )

    def __repr__(self) -> str:
        return f"<ThreatRequirementMapping threat={self.threat_id} req={self.requirement_id} rel={self.relationship_type}>"


class ThreatAuditHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "threat_audit_history"

    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'created', 'accepted', 'rejected', 'edited', 'more_info_requested'
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
    threat: Mapped[Threat] = relationship("Threat", back_populates="history")
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index("ix_threat_hist_threat_id", "threat_id"),
        Index("ix_threat_hist_reviewer", "reviewer_id"),
        Index("ix_threat_hist_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ThreatAuditHistory id={self.id} threat={self.threat_id} action={self.action}>"


class ThreatEvidenceReference(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "threat_evidence_references"

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
    threat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threats.id", ondelete="CASCADE"),
        nullable=False,
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
    evidence_classification: Mapped[str] = mapped_column(String(50), default="documented_fact", nullable=False)
    relevance_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    threat: Mapped[Threat] = relationship("Threat", back_populates="evidence_references")
    document: Mapped[AuditDocument] = relationship("AuditDocument")
    chunk: Mapped[Optional[DocumentChunk]] = relationship("DocumentChunk")

    __table_args__ = (
        CheckConstraint(
            "evidence_classification IN ('documented_fact', 'inference', 'unknown', 'contradictory_information')",
            name="ck_threat_ev_class",
        ),
        Index("ix_threat_ev_threat", "threat_id"),
        Index("ix_threat_ev_doc", "audit_document_id"),
        Index("ix_threat_ev_chunk", "document_chunk_id"),
    )

    def __repr__(self) -> str:
        return f"<ThreatEvidenceReference id={self.id} threat={self.threat_id} doc={self.audit_document_id}>"

