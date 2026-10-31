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


class AuditDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_extension: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_text_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    audit: Mapped[Audit] = relationship(
        "Audit",
        back_populates="documents",
        primaryjoin="AuditDocument.audit_id == Audit.id",
        foreign_keys="[AuditDocument.audit_id]",
    )
    audit_run: Mapped[Optional[AuditRun]] = relationship(
        "AuditRun",
        back_populates="documents",
        primaryjoin="AuditDocument.audit_run_id == AuditRun.id",
        foreign_keys="[AuditDocument.audit_run_id]",
    )
    uploader: Mapped[Optional[User]] = relationship("User", foreign_keys=[uploaded_by])
    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index.asc()",
    )

    def __init__(self, **kwargs: Any) -> None:
        if "original_filename" in kwargs and "file_name" not in kwargs:
            kwargs["file_name"] = kwargs["original_filename"]
        elif "file_name" in kwargs and "original_filename" not in kwargs:
            kwargs["original_filename"] = kwargs["file_name"]

        if "storage_key" in kwargs and "storage_path" not in kwargs:
            kwargs["storage_path"] = kwargs["storage_key"]
        elif "storage_path" in kwargs and "storage_key" not in kwargs:
            kwargs["storage_key"] = kwargs["storage_path"]

        if "file_hash_sha256" in kwargs and "checksum_sha256" not in kwargs:
            kwargs["checksum_sha256"] = kwargs["file_hash_sha256"]
        elif "checksum_sha256" in kwargs and "file_hash_sha256" not in kwargs:
            kwargs["file_hash_sha256"] = kwargs["checksum_sha256"]

        if "stored_filename" not in kwargs and "file_name" in kwargs:
            kwargs["stored_filename"] = kwargs["file_name"]

        if "file_extension" not in kwargs and "file_name" in kwargs:
            fname = kwargs["file_name"]
            kwargs["file_extension"] = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

        super().__init__(**kwargs)

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            ondelete="CASCADE",
            name="fk_audit_docs_org_audit",
        ),
        UniqueConstraint("organization_id", "audit_id", "id", name="uq_audit_docs_org_audit_id"),
        CheckConstraint(
            "status IN ('uploaded', 'queued', 'processing', 'indexed', 'completed', 'failed')",
            name="ck_audit_doc_status",
        ),
        Index("ix_audit_docs_org_id", "organization_id"),
        Index("ix_audit_docs_audit_id", "audit_id"),
        Index("ix_audit_docs_run_id", "audit_run_id"),
        Index("ix_audit_docs_status", "status"),
        Index("ix_audit_docs_deleted_at", "deleted_at"),
        Index("ix_audit_docs_checksum", "checksum_sha256"),
    )

    def __repr__(self) -> str:
        return f"<AuditDocument id={self.id} file_name={self.file_name} status={self.status}>"


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_chunks"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    audit_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_documents.id", ondelete="CASCADE"),
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
    document: Mapped[AuditDocument] = relationship("AuditDocument", back_populates="chunks")

    @property
    def document_id(self) -> uuid.UUID:
        return self.audit_document_id

    @document_id.setter
    def document_id(self, val: uuid.UUID) -> None:
        self.audit_document_id = val

    def __init__(self, **kwargs: Any) -> None:
        if "document_id" in kwargs and "audit_document_id" not in kwargs:
            kwargs["audit_document_id"] = kwargs["document_id"]
        elif "audit_document_id" in kwargs and "document_id" not in kwargs:
            kwargs["document_id"] = kwargs["audit_document_id"]
        if "character_count" not in kwargs and "content" in kwargs and kwargs["content"] is not None:
            kwargs["character_count"] = len(kwargs["content"])
        super().__init__(**kwargs)

    __table_args__ = (
        UniqueConstraint("audit_document_id", "chunk_index", name="uq_doc_chunks_doc_chunk_index"),
        Index("ix_doc_chunks_org_id", "organization_id"),
        Index("ix_doc_chunks_audit_id", "audit_id"),
        Index("ix_doc_chunks_run_id", "audit_run_id"),
        Index("ix_doc_chunks_doc_id", "audit_document_id"),
        Index("ix_doc_chunks_page", "page_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc_id={self.audit_document_id} chunk_idx={self.chunk_index}>"
