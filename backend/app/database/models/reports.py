import uuid
from typing import Any, Dict, Optional
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Report(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    generation_status: Mapped[str] = mapped_column(String(50), default="generating", nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    report_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="reports")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.audit_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_reports_org_audit_run",
        ),
        UniqueConstraint("audit_run_id", "version", "format", name="uq_reports_run_version_format"),
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
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} title={self.title} version={self.version} format={self.format}>"

