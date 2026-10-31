from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.identity import User
    from app.database.models.findings import Finding
    from app.database.models.documents import AuditDocument


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
