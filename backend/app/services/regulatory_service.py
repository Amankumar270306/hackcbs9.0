"""Regulatory service managing frameworks, documents, human reviews, and audit mappings."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.regulatory import (
    AuditRequirement,
    RegulatoryDocument,
    RegulatoryDocumentChunk,
    RegulatoryExtractionJob,
    RegulatoryFramework,
    RequirementAuditHistory,
    RequirementSource,
)
from app.database.models.assessments import Requirement
from app.database.models.audits import Audit
from app.database.models.documents import AuditDocument
from app.services.document_chunker import DocumentChunker
from app.services.document_storage import DocumentStorageService
from app.services.docx_extractor import DocxExtractor
from app.services.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class RegulatoryService:
    """Service layer for Regulatory Knowledge Base management."""

    # -------------------------------------------------------------------------
    # Regulatory Frameworks
    # -------------------------------------------------------------------------

    @staticmethod
    def create_framework(
        session: Session,
        name: str,
        short_name: str,
        issuing_authority: str,
        organization_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        jurisdiction: str = "Global",
        framework_type: str = "standard",
        official_source_url: Optional[str] = None,
        version: str = "1.0",
        effective_date: Optional[datetime] = None,
        framework_metadata: Optional[Dict[str, Any]] = None,
    ) -> RegulatoryFramework:
        framework = RegulatoryFramework(
            organization_id=organization_id,
            name=name.strip(),
            short_name=short_name.strip(),
            description=description.strip() if description else None,
            issuing_authority=issuing_authority.strip(),
            jurisdiction=jurisdiction.strip(),
            framework_type=framework_type.strip(),
            official_source_url=official_source_url.strip() if official_source_url else None,
            version=version.strip(),
            effective_date=effective_date,
            status="active",
            framework_metadata=framework_metadata or {},
        )
        session.add(framework)
        session.commit()
        session.refresh(framework)
        return framework

    @staticmethod
    def list_frameworks(
        session: Session,
        organization_id: Optional[uuid.UUID] = None,
        include_system: bool = True,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[RegulatoryFramework]:
        query = select(RegulatoryFramework)

        filters = []
        if organization_id:
            if include_system:
                filters.append(or_(RegulatoryFramework.organization_id == organization_id, RegulatoryFramework.organization_id.is_(None)))
            else:
                filters.append(RegulatoryFramework.organization_id == organization_id)
        elif not include_system:
            filters.append(RegulatoryFramework.organization_id.isnot(None))

        if status:
            filters.append(RegulatoryFramework.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(
                RegulatoryFramework.name.ilike(pattern),
                RegulatoryFramework.short_name.ilike(pattern),
                RegulatoryFramework.issuing_authority.ilike(pattern),
            ))

        if filters:
            query = query.where(*filters)

        query = query.order_by(RegulatoryFramework.name.asc())
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_framework(
        session: Session,
        framework_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Optional[RegulatoryFramework]:
        query = select(RegulatoryFramework).where(RegulatoryFramework.id == framework_id)
        framework = session.execute(query).scalar_one_or_none()
        if not framework:
            return None
        # Access control: system framework (org_id is None) is public; custom requires matching org_id
        if framework.organization_id is not None and organization_id is not None:
            if framework.organization_id != organization_id:
                return None
        return framework

    @staticmethod
    def update_framework(
        session: Session,
        framework_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
        **updates: Any,
    ) -> Optional[RegulatoryFramework]:
        framework = RegulatoryService.get_framework(session, framework_id, organization_id)
        if not framework:
            return None

        allowed_fields = {
            "name", "short_name", "description", "issuing_authority",
            "jurisdiction", "framework_type", "official_source_url",
            "version", "effective_date", "status", "framework_metadata"
        }
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(framework, field, value)

        session.commit()
        session.refresh(framework)
        return framework

    @staticmethod
    def delete_framework(
        session: Session,
        framework_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> bool:
        framework = RegulatoryService.get_framework(session, framework_id, organization_id)
        if not framework:
            return False
        session.delete(framework)
        session.commit()
        return True

    # -------------------------------------------------------------------------
    # Regulatory Documents & Processing
    # -------------------------------------------------------------------------

    @staticmethod
    def upload_and_process_document(
        session: Session,
        framework_id: uuid.UUID,
        file_bytes: bytes,
        original_filename: str,
        title: Optional[str] = None,
        document_number: Optional[str] = None,
        version: str = "1.0",
        source_url: Optional[str] = None,
        issuing_authority: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        uploaded_by: Optional[uuid.UUID] = None,
    ) -> RegulatoryDocument:
        # Validate framework
        framework = RegulatoryService.get_framework(session, framework_id, organization_id)
        if not framework:
            raise ValueError(f"Regulatory Framework {framework_id} not found.")

        # Validate file
        storage_service = DocumentStorageService()
        file_ext = os.path.splitext(original_filename)[1].lower()
        if file_ext not in (".pdf", ".docx", ".doc"):
            raise ValueError(f"Unsupported file format: {file_ext}. Only PDF and DOCX documents are accepted.")

        max_size = getattr(settings, "MAX_FILE_SIZE_BYTES", 50 * 1024 * 1024)
        if len(file_bytes) > max_size:
            raise ValueError(f"File size exceeds maximum permitted limit of {max_size // (1024*1024)}MB.")

        doc_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        doc_title = title.strip() if title else original_filename

        stored_filename = storage_service.generate_stored_filename(original_filename)
        new_doc_id = uuid.uuid4()
        storage_path, storage_key, _ = storage_service.save_file(
            organization_id=organization_id or "system",
            audit_id=framework_id,
            document_id=new_doc_id,
            stored_filename=stored_filename,
            content=file_bytes,
        )

        mime_type = "application/pdf" if file_ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        doc = RegulatoryDocument(
            id=new_doc_id,
            framework_id=framework.id,
            organization_id=organization_id,
            uploaded_by=uploaded_by,
            title=doc_title,
            document_number=document_number,
            version=version,
            source_url=source_url,
            original_filename=original_filename,
            stored_filename=stored_filename,
            storage_key=storage_key,
            file_extension=file_ext,
            file_size_bytes=file_size,
            mime_type=mime_type,
            document_hash=doc_hash,
            issuing_authority=issuing_authority or framework.issuing_authority,
            status="processing",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        try:
            # Extract content
            if file_ext == ".pdf":
                extracted = PDFExtractor.extract_from_file(storage_path)
                chunks = DocumentChunker.chunk_pdf(extracted)
            elif file_ext in (".docx", ".doc"):
                extracted = DocxExtractor.extract_from_file(storage_path)
                chunks = DocumentChunker.chunk_docx(extracted)
            else:
                raise ValueError(f"Unsupported document format: {file_ext}")

            doc.extracted_text = extracted.text
            doc.page_count = extracted.page_count
            doc.doc_metadata = extracted.metadata

            for c in chunks:
                reg_chunk = RegulatoryDocumentChunk(
                    regulatory_document_id=doc.id,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    section_title=c.section_title,
                    token_count=c.token_count,
                    character_count=c.character_count,
                    content=c.content,
                    start_char_offset=c.start_char_offset,
                    end_char_offset=c.end_char_offset,
                    chunk_metadata=c.chunk_metadata,
                )
                session.add(reg_chunk)

            doc.chunk_count = len(chunks)
            doc.status = "completed"
            session.commit()
            session.refresh(doc)
            return doc

        except Exception as proc_err:
            logger.error(f"Failed processing regulatory doc {doc.id}: {str(proc_err)}", exc_info=True)
            doc.status = "failed"
            doc.processing_error = str(proc_err)
            session.commit()
            session.refresh(doc)
            raise

    @staticmethod
    def list_documents(
        session: Session,
        framework_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> List[RegulatoryDocument]:
        query = select(RegulatoryDocument).where(RegulatoryDocument.framework_id == framework_id)
        if organization_id is not None:
            query = query.where(
                or_(
                    RegulatoryDocument.organization_id == organization_id,
                    RegulatoryDocument.organization_id.is_(None),
                )
            )
        query = query.order_by(RegulatoryDocument.created_at.desc())
        return list(session.execute(query).scalars().all())

    @staticmethod
    def get_document(
        session: Session,
        document_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Optional[RegulatoryDocument]:
        query = select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
        doc = session.execute(query).scalar_one_or_none()
        if not doc:
            return None
        if doc.organization_id is not None and organization_id is not None:
            if doc.organization_id != organization_id:
                return None
        return doc

    @staticmethod
    def get_document_chunks(
        session: Session,
        document_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RegulatoryDocumentChunk]:
        query = (
            select(RegulatoryDocumentChunk)
            .where(RegulatoryDocumentChunk.regulatory_document_id == document_id)
            .order_by(RegulatoryDocumentChunk.chunk_index.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(session.execute(query).scalars().all())

    # -------------------------------------------------------------------------
    # Requirement Review Workflow
    # -------------------------------------------------------------------------

    @staticmethod
    def list_requirements(
        session: Session,
        framework_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None,
        review_status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Requirement], int]:
        query = select(Requirement)
        filters = []

        if framework_id:
            filters.append(Requirement.framework_id == framework_id)
        if document_id:
            filters.append(Requirement.regulatory_document_id == document_id)
        if review_status:
            filters.append(Requirement.review_status == review_status)
        if category:
            filters.append(Requirement.category == category)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Requirement.requirement_code.ilike(pattern),
                    Requirement.title.ilike(pattern),
                    Requirement.description.ilike(pattern),
                    Requirement.source_excerpt.ilike(pattern),
                )
            )

        if filters:
            query = query.where(*filters)

        total = len(list(session.execute(query).scalars().all()))
        paginated_query = query.order_by(Requirement.created_at.asc()).offset(offset).limit(limit)
        items = list(session.execute(paginated_query).scalars().all())
        return items, total

    @staticmethod
    def get_requirement(session: Session, requirement_id: uuid.UUID) -> Optional[Requirement]:
        return session.execute(
            select(Requirement).where(Requirement.id == requirement_id)
        ).scalar_one_or_none()

    @staticmethod
    def approve_requirement(
        session: Session,
        requirement_id: uuid.UUID,
        reviewer_id: Optional[uuid.UUID],
        reason: Optional[str] = None,
    ) -> Requirement:
        req = RegulatoryService.get_requirement(session, requirement_id)
        if not req:
            raise ValueError(f"Requirement {requirement_id} not found.")

        prev_status = req.review_status
        req.review_status = "approved"
        req.reviewed_at = datetime.now(timezone.utc)
        req.reviewed_by = reviewer_id

        history = RequirementAuditHistory(
            requirement_id=req.id,
            reviewer_id=reviewer_id,
            action="approved",
            previous_status=prev_status,
            new_status="approved",
            changes={"status": "approved"},
            reason=reason or "Approved by human compliance reviewer.",
        )
        session.add(history)
        session.commit()
        session.refresh(req)
        return req

    @staticmethod
    def reject_requirement(
        session: Session,
        requirement_id: uuid.UUID,
        reviewer_id: Optional[uuid.UUID],
        reason: str,
    ) -> Requirement:
        req = RegulatoryService.get_requirement(session, requirement_id)
        if not req:
            raise ValueError(f"Requirement {requirement_id} not found.")

        prev_status = req.review_status
        req.review_status = "rejected"
        req.reviewed_at = datetime.now(timezone.utc)
        req.reviewed_by = reviewer_id

        history = RequirementAuditHistory(
            requirement_id=req.id,
            reviewer_id=reviewer_id,
            action="rejected",
            previous_status=prev_status,
            new_status="rejected",
            changes={"status": "rejected"},
            reason=reason,
        )
        session.add(history)
        session.commit()
        session.refresh(req)
        return req

    @staticmethod
    def edit_requirement(
        session: Session,
        requirement_id: uuid.UUID,
        reviewer_id: Optional[uuid.UUID],
        updates: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> Requirement:
        req = RegulatoryService.get_requirement(session, requirement_id)
        if not req:
            raise ValueError(f"Requirement {requirement_id} not found.")

        allowed_fields = {
            "title", "requirement_statement", "detailed_description",
            "obligation_type", "category", "subcategory", "applicability",
            "applicability_conditions", "jurisdiction", "source_section"
        }

        changes: Dict[str, Any] = {}
        for k, v in updates.items():
            if k in allowed_fields and hasattr(req, k):
                old_val = getattr(req, k)
                if old_val != v:
                    changes[k] = {"old": old_val, "new": v}
                    setattr(req, k, v)
                    if k == "requirement_statement":
                        req.description = v

        if changes:
            req.reviewed_at = datetime.now(timezone.utc)
            req.reviewed_by = reviewer_id

            history = RequirementAuditHistory(
                requirement_id=req.id,
                reviewer_id=reviewer_id,
                action="edited",
                previous_status=req.review_status,
                new_status=req.review_status,
                changes=changes,
                reason=reason or "Requirement updated by human reviewer.",
            )
            session.add(history)
            session.commit()
            session.refresh(req)

        return req

    @staticmethod
    def request_revision(
        session: Session,
        requirement_id: uuid.UUID,
        reviewer_id: Optional[uuid.UUID],
        reason: str,
    ) -> Requirement:
        req = RegulatoryService.get_requirement(session, requirement_id)
        if not req:
            raise ValueError(f"Requirement {requirement_id} not found.")

        prev_status = req.review_status
        req.review_status = "needs_revision"
        req.reviewed_at = datetime.now(timezone.utc)
        req.reviewed_by = reviewer_id

        history = RequirementAuditHistory(
            requirement_id=req.id,
            reviewer_id=reviewer_id,
            action="revision_requested",
            previous_status=prev_status,
            new_status="needs_revision",
            changes={"status": "needs_revision"},
            reason=reason,
        )
        session.add(history)
        session.commit()
        session.refresh(req)
        return req

    # -------------------------------------------------------------------------
    # Audit Requirement Mapping & Evidence Matching
    # -------------------------------------------------------------------------

    @staticmethod
    def map_requirements_to_audit(
        session: Session,
        audit_id: uuid.UUID,
        organization_id: uuid.UUID,
        requirement_ids: List[uuid.UUID],
        user_id: Optional[uuid.UUID] = None,
    ) -> List[AuditRequirement]:
        audit = session.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        ).scalar_one_or_none()
        if not audit:
            raise ValueError("Audit not found in organization.")

        created_mappings: List[AuditRequirement] = []
        for req_id in requirement_ids:
            # Check requirement exists
            req = RegulatoryService.get_requirement(session, req_id)
            if not req:
                continue

            # Check if mapping already exists
            existing = session.execute(
                select(AuditRequirement).where(
                    AuditRequirement.audit_id == audit_id,
                    AuditRequirement.requirement_id == req_id,
                )
            ).scalar_one_or_none()

            if not existing:
                mapping = AuditRequirement(
                    organization_id=organization_id,
                    audit_id=audit_id,
                    requirement_id=req_id,
                    applicability_status="applicable",
                    added_by=user_id,
                )
                session.add(mapping)
                created_mappings.append(mapping)

        session.commit()
        return created_mappings

    @staticmethod
    def list_audit_requirements(
        session: Session,
        audit_id: uuid.UUID,
        organization_id: uuid.UUID,
        applicability_status: Optional[str] = None,
    ) -> List[AuditRequirement]:
        query = (
            select(AuditRequirement)
            .where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.organization_id == organization_id,
            )
        )
        if applicability_status:
            query = query.where(AuditRequirement.applicability_status == applicability_status)
        query = query.order_by(AuditRequirement.created_at.desc())
        return list(session.execute(query).scalars().all())

    @staticmethod
    def update_audit_requirement(
        session: Session,
        audit_id: uuid.UUID,
        requirement_id: uuid.UUID,
        organization_id: uuid.UUID,
        applicability_status: str,
        applicability_reason: Optional[str] = None,
    ) -> AuditRequirement:
        mapping = session.execute(
            select(AuditRequirement).where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.requirement_id == requirement_id,
                AuditRequirement.organization_id == organization_id,
            )
        ).scalar_one_or_none()

        if not mapping:
            raise ValueError("Audit requirement mapping not found.")

        mapping.applicability_status = applicability_status
        if applicability_reason is not None:
            mapping.applicability_reason = applicability_reason

        session.commit()
        session.refresh(mapping)
        return mapping

    @staticmethod
    def remove_audit_requirement(
        session: Session,
        audit_id: uuid.UUID,
        requirement_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> bool:
        mapping = session.execute(
            select(AuditRequirement).where(
                AuditRequirement.audit_id == audit_id,
                AuditRequirement.requirement_id == requirement_id,
                AuditRequirement.organization_id == organization_id,
            )
        ).scalar_one_or_none()

        if not mapping:
            return False

        session.delete(mapping)
        session.commit()
        return True

    @staticmethod
    def suggest_audit_evidence(
        session: Session,
        audit_id: uuid.UUID,
        requirement_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Identifies potentially relevant audit documents based on keyword and category overlap."""
        req = RegulatoryService.get_requirement(session, requirement_id)
        if not req:
            return []

        # Fetch all uploaded audit documents for this audit
        docs_stmt = select(AuditDocument).where(
            AuditDocument.audit_id == audit_id,
            AuditDocument.organization_id == organization_id,
            AuditDocument.status == "completed",
        )
        audit_docs = list(session.execute(docs_stmt).scalars().all())

        if not audit_docs:
            return []

        req_keywords = set(
            w.lower()
            for w in f"{req.title} {req.category or ''} {req.subcategory or ''}".split()
            if len(w) > 3
        )

        matches = []
        for doc in audit_docs:
            score = 0.0
            doc_text = (doc.extracted_text or "").lower()
            doc_name = (doc.original_filename or "").lower()

            for kw in req_keywords:
                if kw in doc_name:
                    score += 0.3
                if kw in doc_text:
                    score += 0.2

            if score > 0.0:
                matches.append({
                    "document_id": str(doc.id),
                    "filename": doc.original_filename,
                    "relevance_score": min(round(score, 2), 1.0),
                    "page_count": doc.page_count,
                    "matched_keywords": [kw for kw in req_keywords if kw in doc_text or kw in doc_name],
                })

        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches
