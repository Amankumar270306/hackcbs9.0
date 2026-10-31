import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.reports import Report


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_report(
        self,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        title: str,
        format: str = "pdf",
        version: int = 1,
        storage_path: Optional[str] = None,
        report_metadata: Optional[Dict[str, Any]] = None,
        generation_status: str = "generating",
    ) -> Report:
        report = Report(
            organization_id=organization_id,
            audit_id=audit_id,
            audit_run_id=audit_run_id,
            title=title,
            format=format,
            version=version,
            storage_path=storage_path,
            report_metadata=report_metadata or {},
            generation_status=generation_status,
        )
        self.db.add(report)
        self.db.flush()
        return report

    def get_report(
        self,
        organization_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> Optional[Report]:
        stmt = select(Report).where(
            Report.organization_id == organization_id,
            Report.id == report_id,
        )
        return self.db.scalars(stmt).first()

    def list_reports(
        self,
        organization_id: uuid.UUID,
        audit_id: Optional[uuid.UUID] = None,
    ) -> List[Report]:
        stmt = select(Report).where(Report.organization_id == organization_id)
        if audit_id:
            stmt = stmt.where(Report.audit_id == audit_id)
        stmt = stmt.order_by(Report.created_at.desc())
        return list(self.db.scalars(stmt).all())

