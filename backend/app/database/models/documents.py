from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index.asc()",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.audit_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_audit_docs_org_audit_run",
        ),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_audit_docs_org_run_id"),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'indexed', 'failed')",
            name="ck_audit_doc_status",
        ),
        Index("ix_audit_docs_org_id", "organization_id"),
        Index("ix_audit_docs_run_id", "audit_run_id"),
        Index("ix_audit_docs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AuditDocument id={self.id} file_name={self.file_name} status={self.status}>"


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_chunks"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
    document: Mapped["AuditDocument"] = relationship("AuditDocument", back_populates="chunks")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "audit_document_id"],
            ["audit_documents.organization_id", "audit_documents.audit_run_id", "audit_documents.id"],
            ondelete="CASCADE",
            name="fk_doc_chunks_org_run_doc",
        ),
        UniqueConstraint("audit_document_id", "chunk_index", name="uq_doc_chunks_doc_chunk_index"),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_doc_chunks_org_run_id"),
        Index("ix_doc_chunks_org_id", "organization_id"),
        Index("ix_doc_chunks_run_id", "audit_run_id"),
        Index("ix_doc_chunks_doc_id", "audit_document_id"),
        Index("ix_doc_chunks_page", "page_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc_id={self.audit_document_id} chunk_idx={self.chunk_index}>"

