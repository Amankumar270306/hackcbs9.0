"""Regulatory Knowledge Base database models for Compliance Sentinel.

Defines schemas for:
- RegulatoryFramework: Regulations, standards, and laws (e.g. SOC 2, PCI-DSS, ISO 27001, DPDPA, RBI IT Framework).
- RegulatoryDocument: Authoritative source PDF/DOCX circulars, guidelines, and acts.
- RegulatoryDocumentChunk: Deterministic text chunks extracted from regulatory source documents.
- RequirementSource: Supporting citations, page numbers, and exact text excerpts per requirement.
- AuditRequirement: Association linking approved regulatory requirements to an organization audit.
- RequirementAuditHistory: Traceable audit trail of human edits, reviews, approvals, and rejections.
- RegulatoryExtractionJob: Persisted Legal Analyst agent extraction execution jobs and diagnostics.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
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
    from app.database.models.assessments import Requirement


class RegulatoryFramework(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regulatory_frameworks"

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )  # NULL indicates system-wide / canonical public framework; non-null indicates tenant custom

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issuing_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(100), default="Global", nullable=False)
    framework_type: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    official_source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    framework_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    organization: Mapped[Optional[Organization]] = relationship("Organization")
    documents: Mapped[List[RegulatoryDocument]] = relationship(
        "RegulatoryDocument",
        back_populates="framework",
        cascade="all, delete-orphan",
        order_by="RegulatoryDocument.created_at.desc()",
    )
    requirements: Mapped[List[Requirement]] = relationship(
        "Requirement",
        back_populates="regulatory_framework",
    )

    __table_args__ = (
        CheckConstraint(
            "framework_type IN ('regulation', 'legislation', 'standard', 'guideline', 'circular', 'policy', 'other')",
            name="ck_reg_framework_type",
        ),
        CheckConstraint(
            "status IN ('active', 'draft', 'archived', 'deprecated')",
            name="ck_reg_framework_status",
        ),
        Index("ix_reg_framework_org", "organization_id"),
        Index("ix_reg_framework_short_name", "short_name"),
        Index("ix_reg_framework_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RegulatoryFramework id={self.id} short_name={self.short_name} version={self.version}>"


class RegulatoryDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regulatory_documents"

    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )  # NULL indicates system/shared regulatory document
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    framework: Mapped[RegulatoryFramework] = relationship("RegulatoryFramework", back_populates="documents")
    uploader: Mapped[Optional[User]] = relationship("User", foreign_keys=[uploaded_by])
    chunks: Mapped[List[RegulatoryDocumentChunk]] = relationship(
        "RegulatoryDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RegulatoryDocumentChunk.chunk_index.asc()",
    )
    requirements: Mapped[List[Requirement]] = relationship(
        "Requirement",
        back_populates="regulatory_document",
    )
    extraction_jobs: Mapped[List[RegulatoryExtractionJob]] = relationship(
        "RegulatoryExtractionJob",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RegulatoryExtractionJob.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'completed', 'failed')",
            name="ck_reg_doc_status",
        ),
        Index("ix_reg_docs_framework", "framework_id"),
        Index("ix_reg_docs_org", "organization_id"),
        Index("ix_reg_docs_hash", "document_hash"),
        Index("ix_reg_docs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RegulatoryDocument id={self.id} title={self.title} status={self.status}>"


class RegulatoryDocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "regulatory_document_chunks"

    regulatory_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document: Mapped[RegulatoryDocument] = relationship("RegulatoryDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("regulatory_document_id", "chunk_index", name="uq_reg_chunks_doc_idx"),
        Index("ix_reg_chunks_doc", "regulatory_document_id"),
        Index("ix_reg_chunks_page", "page_number"),
    )

    def __repr__(self) -> str:
        return f"<RegulatoryDocumentChunk id={self.id} doc={self.regulatory_document_id} idx={self.chunk_index}>"


class RequirementSource(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "requirement_sources"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    regulatory_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )

    section_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exact_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="primary_clause", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    requirement: Mapped[Requirement] = relationship("Requirement", back_populates="sources")
    document: Mapped[RegulatoryDocument] = relationship("RegulatoryDocument")
    chunk: Mapped[Optional[RegulatoryDocumentChunk]] = relationship("RegulatoryDocumentChunk")

    __table_args__ = (
        Index("ix_req_sources_req_id", "requirement_id"),
        Index("ix_req_sources_doc_id", "regulatory_document_id"),
        Index("ix_req_sources_chunk_id", "document_chunk_id"),
    )

    def __repr__(self) -> str:
        return f"<RequirementSource id={self.id} req={self.requirement_id} doc={self.regulatory_document_id}>"


class AuditRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_requirements"

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
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    applicability_status: Mapped[str] = mapped_column(String(50), default="applicable", nullable=False)
    applicability_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    audit: Mapped[Audit] = relationship("Audit", back_populates="audit_requirements", foreign_keys=[audit_id])
    requirement: Mapped[Requirement] = relationship("Requirement", back_populates="audit_mappings", foreign_keys=[requirement_id])
    adder: Mapped[Optional[User]] = relationship("User", foreign_keys=[added_by])

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            ondelete="CASCADE",
            name="fk_audit_req_org_audit",
        ),
        UniqueConstraint("audit_id", "requirement_id", name="uq_audit_requirements_audit_req"),
        CheckConstraint(
            "applicability_status IN ('applicable', 'not_applicable', 'requires_review')",
            name="ck_audit_req_applicability",
        ),
        Index("ix_audit_req_org", "organization_id"),
        Index("ix_audit_req_audit", "audit_id"),
        Index("ix_audit_req_requirement", "requirement_id"),
        Index("ix_audit_req_status", "applicability_status"),
    )

    def __repr__(self) -> str:
        return f"<AuditRequirement id={self.id} audit={self.audit_id} req={self.requirement_id} status={self.applicability_status}>"


class RequirementAuditHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "requirement_audit_history"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'created', 'edited', 'approved', 'rejected', 'revision_requested'
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
    requirement: Mapped[Requirement] = relationship("Requirement", back_populates="history")
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index("ix_req_hist_req_id", "requirement_id"),
        Index("ix_req_hist_reviewer", "reviewer_id"),
        Index("ix_req_hist_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<RequirementAuditHistory id={self.id} req={self.requirement_id} action={self.action}>"


class RegulatoryExtractionJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "regulatory_extraction_jobs"

    regulatory_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulatory_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    chunks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunks_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requirements_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    document: Mapped[RegulatoryDocument] = relationship("RegulatoryDocument", back_populates="extraction_jobs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_reg_job_status",
        ),
        Index("ix_reg_jobs_doc", "regulatory_document_id"),
        Index("ix_reg_jobs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RegulatoryExtractionJob id={self.id} doc={self.regulatory_document_id} status={self.status}>"
