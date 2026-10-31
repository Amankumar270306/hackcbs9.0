from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    from app.database.models.adjudication import AdjudicationRun
    from app.database.models.audits import Audit, AuditRun
    from app.database.models.identity import User


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    adjudication_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("adjudication_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    format: Mapped[str] = mapped_column(String(50), default="pdf", nullable=False)
    generation_status: Mapped[str] = mapped_column(String(50), default="generating", nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    report_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    audit: Mapped[Audit] = relationship("Audit", back_populates="reports", foreign_keys=[audit_id], overlaps="reports")
    audit_run: Mapped[Optional[AuditRun]] = relationship("AuditRun", back_populates="reports", foreign_keys=[audit_run_id], overlaps="reports,audit")
    adjudication_run: Mapped[Optional[AdjudicationRun]] = relationship("AdjudicationRun", back_populates="reports", foreign_keys=[adjudication_run_id])
    creator: Mapped[Optional[User]] = relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            ondelete="CASCADE",
            name="fk_reports_org_audit",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.audit_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_reports_org_audit_run",
        ),
        CheckConstraint(
            "format IN ('pdf', 'html', 'json', 'markdown')",
            name="ck_reports_format",
        ),
        CheckConstraint(
            "generation_status IN ('generating', 'completed', 'failed')",
            name="ck_reports_generation_status",
        ),
        Index("ix_reports_org_id", "organization_id"),
        Index("ix_reports_audit_id", "audit_id"),
        Index("ix_reports_run_id", "audit_run_id"),
        Index("ix_reports_status", "generation_status"),
        Index("ix_reports_adj_run", "adjudication_run_id"),
        Index("ix_reports_audit_version", "audit_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} title={self.title} version={self.version} format={self.format} status={self.generation_status}>"
