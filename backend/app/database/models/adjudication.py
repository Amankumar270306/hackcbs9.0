"""Database models for Adjudicator: Cross-Agent Consensus, Evidence Reconciliation & Contradiction Resolution (Milestone 7)."""

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
    from app.database.models.audits import Audit
    from app.database.models.documents import AuditDocument
    from app.database.models.findings import Finding
    from app.database.models.identity import Organization, User
    from app.database.models.reports import Report


# ---------------------------------------------------------------------------
# Legacy Milestone 1 Models (Preserved for compatibility)
# ---------------------------------------------------------------------------


class AdjudicationQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "adjudication_questions"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Relationships
    answers: Mapped[List[AdjudicationAnswer]] = relationship(
        "AdjudicationAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_adj_questions_org_run",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "finding_id"],
            ["findings.organization_id", "findings.audit_run_id", "findings.id"],
            ondelete="CASCADE",
            name="fk_adj_questions_org_run_finding",
        ),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_adj_questions_org_run_id"),
        CheckConstraint(
            "status IN ('pending', 'answered', 'dismissed')",
            name="ck_adj_questions_status",
        ),
        Index("ix_adj_questions_org_id", "organization_id"),
        Index("ix_adj_questions_run_id", "audit_run_id"),
        Index("ix_adj_questions_finding_id", "finding_id"),
        Index("ix_adj_questions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationQuestion id={self.id} status={self.status}>"


class AdjudicationAnswer(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "adjudication_answers"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    question: Mapped[AdjudicationQuestion] = relationship("AdjudicationQuestion", back_populates="answers")
    user: Mapped[User] = relationship("User")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "question_id"],
            ["adjudication_questions.organization_id", "adjudication_questions.audit_run_id", "adjudication_questions.id"],
            ondelete="CASCADE",
            name="fk_adj_answers_org_run_question",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "evidence_document_id"],
            ["audit_documents.organization_id", "audit_documents.audit_run_id", "audit_documents.id"],
            ondelete="RESTRICT",
            name="fk_adj_answers_org_run_doc",
        ),
        Index("ix_adj_answers_org_id", "organization_id"),
        Index("ix_adj_answers_run_id", "audit_run_id"),
        Index("ix_adj_answers_question_id", "question_id"),
        Index("ix_adj_answers_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationAnswer id={self.id} question_id={self.question_id}>"


# ---------------------------------------------------------------------------
# Milestone 7: Adjudicator Core Models
# ---------------------------------------------------------------------------


class AdjudicationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An execution run of the Adjudicator agent reconciling outputs across all agents."""

    __tablename__ = "adjudication_runs"

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

    input_source_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    requirements_processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    threats_processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    controls_processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    decisions_generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contradictions_detected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="adjudication_runs")
    decisions: Mapped[List[AdjudicationDecision]] = relationship(
        "AdjudicationDecision",
        back_populates="adjudication_run",
        cascade="all, delete-orphan",
    )
    contradictions: Mapped[List[AdjudicationContradiction]] = relationship(
        "AdjudicationContradiction",
        back_populates="adjudication_run",
        cascade="all, delete-orphan",
    )
    reports: Mapped[List[Report]] = relationship(
        "Report",
        back_populates="adjudication_run",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_adjudication_run_status",
        ),
        Index("ix_adj_runs_org", "organization_id"),
        Index("ix_adj_runs_audit", "audit_id"),
        Index("ix_adj_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationRun id={self.id} audit={self.audit_id} status={self.status}>"


class AdjudicationDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured reconciliation decision produced by the Adjudicator for a requirement, threat, control, or finding."""

    __tablename__ = "adjudication_decisions"

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
    adjudication_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    decision_category: Mapped[str] = mapped_column(String(50), nullable=False)
    related_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    outcome_status: Mapped[str] = mapped_column(String(60), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(4, 2), default=0.50, nullable=False)

    is_provisional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    evidence_limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assumptions: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    missing_information: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    review_status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="adjudication_decisions")
    adjudication_run: Mapped[AdjudicationRun] = relationship("AdjudicationRun", back_populates="decisions")
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewed_by])
    sources: Mapped[List[AdjudicationSource]] = relationship(
        "AdjudicationSource",
        back_populates="decision",
        cascade="all, delete-orphan",
    )
    audit_history: Mapped[List[AdjudicationAuditHistory]] = relationship(
        "AdjudicationAuditHistory",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="AdjudicationAuditHistory.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "decision_category IN ('requirement_compliance', 'threat_mitigation', 'control_effectiveness', 'cross_cutting')",
            name="ck_adj_decision_category",
        ),
        CheckConstraint(
            "related_entity_type IN ('requirement', 'threat', 'control', 'general')",
            name="ck_adj_decision_entity_type",
        ),
        CheckConstraint(
            "outcome_status IN ("
            "'supported_by_documented_evidence', "
            "'partially_supported', "
            "'insufficient_evidence', "
            "'contradictory_evidence', "
            "'documented_nonconformance', "
            "'not_applicable', "
            "'requires_human_review', "
            "'documented_mitigations_supported', "
            "'partially_mitigated', "
            "'insufficient_mitigation_evidence', "
            "'documented_control_weakness'"
            ")",
            name="ck_adj_decision_outcome",
        ),
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected', 'edited', 'more_info_requested')",
            name="ck_adj_decision_review_status",
        ),
        Index("ix_adj_decisions_org", "organization_id"),
        Index("ix_adj_decisions_audit", "audit_id"),
        Index("ix_adj_decisions_run", "adjudication_run_id"),
        Index("ix_adj_decisions_category", "decision_category"),
        Index("ix_adj_decisions_entity", "related_entity_type", "related_entity_id"),
        Index("ix_adj_decisions_outcome", "outcome_status"),
        Index("ix_adj_decisions_review", "review_status"),
        Index("ix_adj_decisions_stale", "is_stale"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationDecision id={self.id} category={self.decision_category} outcome={self.outcome_status}>"


class AdjudicationSource(Base, UUIDPrimaryKeyMixin):
    """Link between an adjudication decision and its underlying source records across all agents."""

    __tablename__ = "adjudication_sources"

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
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_decisions.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_agent: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    source_role: Mapped[str] = mapped_column(String(50), default="supporting", nullable=False)
    citation_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exact_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_citation_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    citation_validation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    decision: Mapped[AdjudicationDecision] = relationship("AdjudicationDecision", back_populates="sources")

    __table_args__ = (
        CheckConstraint(
            "source_agent IN ('legal_analyst', 'adversarial_strategist', 'defence_auditor', 'document_extractor', 'human_reviewer')",
            name="ck_adj_source_agent",
        ),
        CheckConstraint(
            "source_entity_type IN ('regulatory_requirement', 'threat_scenario', 'discovered_control', 'control_assessment', 'finding', 'document_chunk')",
            name="ck_adj_source_entity_type",
        ),
        CheckConstraint(
            "source_role IN ('supporting', 'contradictory', 'contextual', 'informational')",
            name="ck_adj_source_role",
        ),
        Index("ix_adj_sources_org", "organization_id"),
        Index("ix_adj_sources_audit", "audit_id"),
        Index("ix_adj_sources_decision", "decision_id"),
        Index("ix_adj_sources_entity", "source_entity_type", "source_entity_id"),
        Index("ix_adj_sources_validity", "is_citation_valid"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationSource id={self.id} agent={self.source_agent} entity={self.source_entity_type}>"


class AdjudicationContradiction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Contradiction or conflict detected across agents or document sources during adjudication."""

    __tablename__ = "adjudication_contradictions"

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
    adjudication_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    contradiction_category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    conflicting_claims: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    impact: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(50), default="unresolved", nullable=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    audit: Mapped[Audit] = relationship("Audit", back_populates="adjudication_contradictions")
    adjudication_run: Mapped[AdjudicationRun] = relationship("AdjudicationRun", back_populates="contradictions")
    resolver: Mapped[Optional[User]] = relationship("User", foreign_keys=[resolved_by])
    audit_history: Mapped[List[AdjudicationAuditHistory]] = relationship(
        "AdjudicationAuditHistory",
        back_populates="contradiction",
        cascade="all, delete-orphan",
        order_by="AdjudicationAuditHistory.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "contradiction_category IN ('requirement_vs_control', 'threat_vs_control', 'contradictory_documents', 'ai_vs_human_review', 'cross_agent')",
            name="ck_adj_contradiction_category",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="ck_adj_contradiction_severity",
        ),
        CheckConstraint(
            "resolution_status IN ('unresolved', 'resolved', 'clarification_requested', 'dismissed')",
            name="ck_adj_contradiction_resolution",
        ),
        Index("ix_adj_contra_org", "organization_id"),
        Index("ix_adj_contra_audit", "audit_id"),
        Index("ix_adj_contra_run", "adjudication_run_id"),
        Index("ix_adj_contra_category", "contradiction_category"),
        Index("ix_adj_contra_status", "resolution_status"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationContradiction id={self.id} category={self.contradiction_category} status={self.resolution_status}>"


class AdjudicationAuditHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail for human review actions on adjudication decisions and contradictions."""

    __tablename__ = "adjudication_audit_history"

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
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_decisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    contradiction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_contradictions.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    updated_content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    decision: Mapped[Optional[AdjudicationDecision]] = relationship("AdjudicationDecision", back_populates="audit_history")
    contradiction: Mapped[Optional[AdjudicationContradiction]] = relationship("AdjudicationContradiction", back_populates="audit_history")
    user: Mapped[User] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "action IN ('approved', 'rejected', 'edited', 'requested_information', 'resolved_contradiction', 'reassessed', 'marked_unresolved')",
            name="ck_adj_history_action",
        ),
        Index("ix_adj_history_org", "organization_id"),
        Index("ix_adj_history_audit", "audit_id"),
        Index("ix_adj_history_decision", "decision_id"),
        Index("ix_adj_history_contradiction", "contradiction_id"),
        Index("ix_adj_history_user", "user_id"),
        Index("ix_adj_history_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AdjudicationAuditHistory id={self.id} action={self.action} status={self.new_status}>"
