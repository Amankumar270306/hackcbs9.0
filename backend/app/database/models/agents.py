from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    n8n_execution_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="agent_runs")
    events: Mapped[List["AgentEvent"]] = relationship(
        "AgentEvent",
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="AgentEvent.created_at.asc()",
    )
    outputs: Mapped[List["AgentOutput"]] = relationship(
        "AgentOutput",
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id"],
            ["audit_runs.organization_id", "audit_runs.id"],
            ondelete="CASCADE",
            name="fk_agent_runs_org_run",
        ),
        UniqueConstraint("organization_id", "audit_run_id", "id", name="uq_agent_runs_org_run_id"),
        CheckConstraint(
            "agent_type IN ('legal_analyst', 'adversarial_strategist', 'defence_auditor', 'adjudicator', 'report_generator')",
            name="ck_agent_runs_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_org_id", "organization_id"),
        Index("ix_agent_runs_run_id", "audit_run_id"),
        Index("ix_agent_runs_type", "agent_type"),
        Index("ix_agent_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AgentRun id={self.id} type={self.agent_type} status={self.status}>"


class AgentEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="events")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.audit_run_id", "agent_runs.id"],
            ondelete="CASCADE",
            name="fk_agent_events_org_run_agent",
        ),
        Index("ix_agent_events_org_id", "organization_id"),
        Index("ix_agent_events_run_id", "audit_run_id"),
        Index("ix_agent_events_agent_run_id", "agent_run_id"),
        Index("ix_agent_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AgentEvent id={self.id} type={self.event_type}>"


class AgentOutput(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_outputs"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    output_type: Mapped[str] = mapped_column(String(100), nullable=False)
    structured_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="outputs")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "audit_run_id", "agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.audit_run_id", "agent_runs.id"],
            ondelete="CASCADE",
            name="fk_agent_outputs_org_run_agent",
        ),
        Index("ix_agent_outputs_org_id", "organization_id"),
        Index("ix_agent_outputs_run_id", "audit_run_id"),
        Index("ix_agent_outputs_agent_run_id", "agent_run_id"),
        Index("ix_agent_outputs_type", "output_type"),
    )

    def __repr__(self) -> str:
        return f"<AgentOutput id={self.id} type={self.output_type}>"

