import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.audits import Audit, AuditRun


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_audit(
        self,
        organization_id: uuid.UUID,
        title: str,
        target_system: str,
        environment: str = "production",
        description: Optional[str] = None,
    ) -> Audit:
        audit = Audit(
            organization_id=organization_id,
            title=title,
            target_system=target_system,
            environment=environment,
            description=description,
        )
        self.db.add(audit)
        self.db.flush()
        return audit

    def get_audit(self, organization_id: uuid.UUID, audit_id: uuid.UUID) -> Optional[Audit]:
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        return self.db.scalars(stmt).first()

    def list_audits(self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> List[Audit]:
        stmt = (
            select(Audit)
            .where(Audit.organization_id == organization_id)
            .order_by(Audit.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def create_audit_run(
        self,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        status: str = "pending",
        summary: Optional[str] = None,
    ) -> AuditRun:
        # Determine next run number
        stmt = (
            select(AuditRun.run_number)
            .where(
                AuditRun.organization_id == organization_id,
                AuditRun.audit_id == audit_id,
            )
            .order_by(AuditRun.run_number.desc())
            .limit(1)
        )
        last_run = self.db.scalars(stmt).first()
        next_run_number = (last_run or 0) + 1

        audit_run = AuditRun(
            organization_id=organization_id,
            audit_id=audit_id,
            run_number=next_run_number,
            status=status,
            summary=summary,
        )
        self.db.add(audit_run)
        self.db.flush()
        return audit_run

    def get_audit_run(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
    ) -> Optional[AuditRun]:
        stmt = select(AuditRun).where(
            AuditRun.organization_id == organization_id,
            AuditRun.id == audit_run_id,
        )
        return self.db.scalars(stmt).first()

