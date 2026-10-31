from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.audits import Audit, AuditRun
from app.database.models.documents import AuditDocument
from app.database.models.findings import Finding
from app.schemas.audit_runs import AuditRunCreate, AuditRunResponse
from app.schemas.audits import AuditCreate, AuditResponse, AuditUpdate


class AuditService:
    @staticmethod
    def create_audit(
        db: Session,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AuditCreate,
    ) -> AuditResponse:
        """Create a new audit within an organization."""
        audit = Audit(
            organization_id=organization_id,
            title=data.name.strip(),
            name=data.name.strip(),
            application_name=data.application_name.strip(),
            target_system=data.application_name.strip(),
            description=data.description.strip() if data.description else None,
            environment="production",
            status="draft",
            created_by=user_id,
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)

        return AuditResponse(
            id=audit.id,
            organization_id=audit.organization_id,
            name=audit.name or audit.title,
            application_name=audit.application_name or audit.target_system,
            description=audit.description,
            status=audit.status,
            created_by=audit.created_by,
            created_at=audit.created_at,
            updated_at=audit.updated_at,
            runs_count=0,
            document_count=0,
            finding_count=0,
            latest_run=None,
        )

    @staticmethod
    def list_audits(
        db: Session,
        organization_id: uuid.UUID,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[AuditResponse], int]:
        """List audits for an organization with pagination, filtering, and summary statistics."""
        query = select(Audit).where(Audit.organization_id == organization_id)

        if status_filter and status_filter.lower() != "all":
            query = query.where(Audit.status == status_filter.lower())
        else:
            # Exclude archived by default if no explicit filter is given
            query = query.where(Audit.status != "archived")

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Audit.name.ilike(term),
                    Audit.title.ilike(term),
                    Audit.application_name.ilike(term),
                    Audit.target_system.ilike(term),
                    Audit.description.ilike(term),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_stmt) or 0

        # Paginate
        offset = max(0, (page - 1) * size)
        stmt = (
            query.order_by(Audit.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        audits = db.scalars(stmt).all()

        results = []
        for audit in audits:
            # Runs count & latest run
            runs_stmt = (
                select(AuditRun)
                .where(
                    AuditRun.organization_id == organization_id,
                    AuditRun.audit_id == audit.id,
                )
                .order_by(AuditRun.run_number.desc())
            )
            runs = db.scalars(runs_stmt).all()
            runs_count = len(runs)
            latest_run = None
            if runs:
                lr = runs[0]
                latest_run = {
                    "id": str(lr.id),
                    "run_number": lr.run_number,
                    "status": lr.status,
                    "risk_score": float(lr.risk_score) if lr.risk_score is not None else None,
                    "summary": lr.summary,
                    "created_at": lr.created_at.isoformat() if lr.created_at else None,
                }

            # Document count
            doc_count_stmt = select(func.count()).select_from(AuditDocument).where(
                AuditDocument.organization_id == organization_id,
                AuditDocument.audit_id == audit.id,
                AuditDocument.deleted_at.is_(None),
            )
            doc_count = db.scalar(doc_count_stmt) or 0

            # Finding count across runs of this audit
            run_ids = [r.id for r in runs]
            finding_count = 0
            if run_ids:
                finding_count_stmt = select(func.count()).select_from(Finding).where(
                    Finding.organization_id == organization_id,
                    Finding.audit_run_id.in_(run_ids),
                )
                finding_count = db.scalar(finding_count_stmt) or 0

            results.append(
                AuditResponse(
                    id=audit.id,
                    organization_id=audit.organization_id,
                    name=audit.name or audit.title,
                    application_name=audit.application_name or audit.target_system,
                    description=audit.description,
                    status=audit.status,
                    created_by=audit.created_by,
                    created_at=audit.created_at,
                    updated_at=audit.updated_at,
                    runs_count=runs_count,
                    document_count=doc_count,
                    finding_count=finding_count,
                    latest_run=latest_run,
                )
            )

        return results, total

    @staticmethod
    def get_audit(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> AuditResponse:
        """Get an audit by ID with detailed statistics."""
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        audit = db.scalars(stmt).first()
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found",
            )

        # Runs count & latest run
        runs_stmt = (
            select(AuditRun)
            .where(
                AuditRun.organization_id == organization_id,
                AuditRun.audit_id == audit.id,
            )
            .order_by(AuditRun.run_number.desc())
        )
        runs = db.scalars(runs_stmt).all()
        runs_count = len(runs)
        latest_run = None
        if runs:
            lr = runs[0]
            latest_run = {
                "id": str(lr.id),
                "run_number": lr.run_number,
                "status": lr.status,
                "risk_score": float(lr.risk_score) if lr.risk_score is not None else None,
                "summary": lr.summary,
                "created_at": lr.created_at.isoformat() if lr.created_at else None,
            }

        # Document count
        doc_count_stmt = select(func.count()).select_from(AuditDocument).where(
            AuditDocument.organization_id == organization_id,
            AuditDocument.audit_id == audit.id,
            AuditDocument.deleted_at.is_(None),
        )
        doc_count = db.scalar(doc_count_stmt) or 0

        # Finding count
        run_ids = [r.id for r in runs]
        finding_count = 0
        if run_ids:
            finding_count_stmt = select(func.count()).select_from(Finding).where(
                Finding.organization_id == organization_id,
                Finding.audit_run_id.in_(run_ids),
            )
            finding_count = db.scalar(finding_count_stmt) or 0

        return AuditResponse(
            id=audit.id,
            organization_id=audit.organization_id,
            name=audit.name or audit.title,
            application_name=audit.application_name or audit.target_system,
            description=audit.description,
            status=audit.status,
            created_by=audit.created_by,
            created_at=audit.created_at,
            updated_at=audit.updated_at,
            runs_count=runs_count,
            document_count=doc_count,
            finding_count=finding_count,
            latest_run=latest_run,
        )

    @staticmethod
    def update_audit(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        data: AuditUpdate,
    ) -> AuditResponse:
        """Update audit fields."""
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        audit = db.scalars(stmt).first()
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found",
            )

        if data.name:
            audit.name = data.name.strip()
            audit.title = data.name.strip()
        if data.application_name:
            audit.application_name = data.application_name.strip()
            audit.target_system = data.application_name.strip()
        if data.description is not None:
            audit.description = data.description.strip() if data.description else None

        db.commit()
        db.refresh(audit)
        return AuditService.get_audit(db, organization_id, audit_id)

    @staticmethod
    def archive_audit(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> None:
        """Archive an audit (soft delete preserving history)."""
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        audit = db.scalars(stmt).first()
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found",
            )

        audit.status = "archived"
        db.commit()

    @staticmethod
    def create_audit_run(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AuditRunCreate,
    ) -> AuditRunResponse:
        """Create a new sequential audit run safely allocating run_number."""
        # Ensure audit exists and belongs to this organization
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        audit = db.scalars(stmt).first()
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found",
            )

        # Allocate next run number
        max_run_stmt = select(func.coalesce(func.max(AuditRun.run_number), 0)).where(
            AuditRun.organization_id == organization_id,
            AuditRun.audit_id == audit_id,
        )
        last_run_number = db.scalar(max_run_stmt) or 0
        next_run_number = last_run_number + 1

        run = AuditRun(
            organization_id=organization_id,
            audit_id=audit_id,
            run_number=next_run_number,
            status="queued",
            summary=data.summary.strip() if data.summary else None,
            config=data.config or {},
            created_by=user_id,
        )
        db.add(run)

        # Update audit status from draft to active if needed
        if audit.status == "draft":
            audit.status = "active"

        db.commit()
        db.refresh(run)

        return AuditRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            audit_id=run.audit_id,
            run_number=run.run_number,
            status=run.status,
            risk_score=float(run.risk_score) if run.risk_score is not None else None,
            summary=run.summary,
            config=run.config or {},
            created_by=run.created_by,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )

    @staticmethod
    def list_audit_runs(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
    ) -> List[AuditRunResponse]:
        """List all runs for an audit."""
        # Verify audit exists
        stmt = select(Audit).where(
            Audit.organization_id == organization_id,
            Audit.id == audit_id,
        )
        if db.scalars(stmt).first() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found",
            )

        runs_stmt = (
            select(AuditRun)
            .where(
                AuditRun.organization_id == organization_id,
                AuditRun.audit_id == audit_id,
            )
            .order_by(AuditRun.run_number.desc())
        )
        runs = db.scalars(runs_stmt).all()

        return [
            AuditRunResponse(
                id=r.id,
                organization_id=r.organization_id,
                audit_id=r.audit_id,
                run_number=r.run_number,
                status=r.status,
                risk_score=float(r.risk_score) if r.risk_score is not None else None,
                summary=r.summary,
                config=r.config or {},
                created_by=r.created_by,
                started_at=r.started_at,
                completed_at=r.completed_at,
                created_at=r.created_at,
            )
            for r in runs
        ]

    @staticmethod
    def get_audit_run(
        db: Session,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> AuditRunResponse:
        """Get a specific audit run."""
        stmt = select(AuditRun).where(
            AuditRun.organization_id == organization_id,
            AuditRun.audit_id == audit_id,
            AuditRun.id == run_id,
        )
        run = db.scalars(stmt).first()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit run not found",
            )

        return AuditRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            audit_id=run.audit_id,
            run_number=run.run_number,
            status=run.status,
            risk_score=float(run.risk_score) if run.risk_score is not None else None,
            summary=run.summary,
            config=run.config or {},
            created_by=run.created_by,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )

