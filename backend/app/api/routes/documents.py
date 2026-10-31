"""Document management API endpoints for Compliance Sentinel.

Provides secure multi-tenant upload, listing, inspection, chunk retrieval,
download, retry processing, and safe deletion of documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Optional
import urllib.parse
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_membership, get_current_user, require_roles
from app.database.connection import SessionLocal, get_db
from app.database.models.audits import Audit
from app.database.models.documents import AuditDocument, DocumentChunk
from app.database.models.identity import OrganizationMember, User
from app.schemas.documents import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentTextResponse,
)
from app.services.document_processor import document_processor
from app.services.document_storage import storage_service

router = APIRouter(
    prefix="/api/organizations/{organization_id}/audits/{audit_id}/documents",
    tags=["Documents"],
)


def _get_audit_or_404(db: Session, organization_id: uuid.UUID, audit_id: uuid.UUID) -> Audit:
    """Verify audit exists and belongs strictly to the organization."""
    audit = db.execute(
        select(Audit).where(
            Audit.id == audit_id,
            Audit.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found in this organization",
        )
    return audit


def _get_document_or_404(
    db: Session,
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    allow_deleted: bool = False,
) -> AuditDocument:
    """Retrieve document ensuring strict tenant and audit isolation."""
    query = select(AuditDocument).where(
        AuditDocument.id == document_id,
        AuditDocument.audit_id == audit_id,
        AuditDocument.organization_id == organization_id,
    )
    if not allow_deleted:
        query = query.where(AuditDocument.deleted_at.is_(None))

    doc = db.execute(query).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or has been deleted",
        )
    return doc


def _process_document_in_background(document_id: uuid.UUID) -> None:
    """Background task runner with dedicated session handling."""
    db = SessionLocal()
    try:
        document_processor.process_document_pipeline(db, document_id)
    finally:
        db.close()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a PDF or DOCX compliance document for an audit.

    Validates file content (magic bytes), checks maximum size, enforces duplicate
    prevention via SHA-256 within the audit, stores file persistently, and triggers
    background extraction and chunking.
    """
    _get_audit_or_404(db, organization_id, audit_id)

    # 1. Bounded read, magic bytes validation & SHA-256 hashing
    content_bytes, sha256_hash, ext, file_size = await document_processor.inspect_and_read_upload(file)

    # 2. Check for duplicate upload within the same audit
    document_processor.check_duplicate(db, audit_id, sha256_hash)

    # 3. Generate storage keys and server-side random filename
    document_id = uuid.uuid4()
    original_filename = file.filename or f"upload.{ext}"
    stored_filename = storage_service.generate_stored_filename(original_filename)

    storage_path, storage_key, _ = storage_service.save_file(
        organization_id=organization_id,
        audit_id=audit_id,
        document_id=document_id,
        stored_filename=stored_filename,
        content=content_bytes,
    )

    mime_type = "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 4. Create document database record
    doc = AuditDocument(
        id=document_id,
        organization_id=organization_id,
        audit_id=audit_id,
        uploaded_by=current_user.id,
        file_name=original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_extension=ext,
        file_size_bytes=file_size,
        mime_type=mime_type,
        storage_path=storage_path,
        storage_key=storage_key,
        checksum_sha256=sha256_hash,
        file_hash_sha256=sha256_hash,
        status="uploaded",
        doc_metadata={
            "original_filename": original_filename,
            "uploader_email": current_user.email,
        },
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 5. Enqueue background processing
    background_tasks.add_task(_process_document_in_background, doc.id)

    return doc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    search: Optional[str] = Query(None, description="Search by document original filename"),
    status: Optional[str] = Query(None, description="Filter by status (uploaded, queued, processing, completed, failed)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List all active documents belonging to an audit with search, status filtering, and pagination."""
    _get_audit_or_404(db, organization_id, audit_id)

    base_filter = [
        AuditDocument.organization_id == organization_id,
        AuditDocument.audit_id == audit_id,
        AuditDocument.deleted_at.is_(None),
    ]

    if search:
        search_term = f"%{search}%"
        base_filter.append(
            (AuditDocument.original_filename.ilike(search_term)) | (AuditDocument.file_name.ilike(search_term))
        )

    if status and status.lower() != "all":
        base_filter.append(AuditDocument.status == status.lower())

    total_query = select(func.count(AuditDocument.id)).where(*base_filter)
    total = db.scalar(total_query) or 0

    size_query = select(func.coalesce(func.sum(AuditDocument.file_size_bytes), 0)).where(*base_filter)
    total_file_size = db.scalar(size_query) or 0

    offset = (page - 1) * size
    docs_query = (
        select(AuditDocument)
        .where(*base_filter)
        .order_by(AuditDocument.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    docs = db.scalars(docs_query).all()

    total_pages = math.ceil(total / size) if total > 0 else 1

    return DocumentListResponse(
        items=list(docs),
        total=total,
        page=page,
        size=size,
        pages=total_pages,
        total_file_size_bytes=total_file_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Get metadata, extraction statistics, and details of a specific document."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)
    return doc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Get real-time document processing status and metrics."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)
    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        processing_error=doc.processing_error,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        extracted_text_length=doc.extracted_text_length,
        processed_at=doc.processed_at,
    )


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_document_extracted_text(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Retrieve the full extracted text representation for preview."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)
    return DocumentTextResponse(
        document_id=doc.id,
        original_filename=doc.original_filename or doc.file_name,
        extracted_text=doc.extracted_text,
        extracted_text_length=doc.extracted_text_length,
        page_count=doc.page_count,
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def list_document_chunks(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    page_number: Optional[int] = Query(None, description="Filter chunks by page number"),
    section: Optional[str] = Query(None, description="Filter chunks by section title"),
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """List paginated document chunks with source traceability (page, section, character offsets)."""
    _get_audit_or_404(db, organization_id, audit_id)
    _get_document_or_404(db, organization_id, audit_id, document_id)

    filters = [DocumentChunk.audit_document_id == document_id]
    if page_number is not None:
        filters.append(
            (DocumentChunk.page_number == page_number)
            | (
                (DocumentChunk.page_start <= page_number)
                & (DocumentChunk.page_end >= page_number)
            )
        )
    if section:
        filters.append(DocumentChunk.section_title.ilike(f"%{section}%"))

    total = db.scalar(select(func.count(DocumentChunk.id)).where(*filters)) or 0
    total_pages = math.ceil(total / size) if total > 0 else 1

    offset = (page - 1) * size
    chunks = (
        db.scalars(
            select(DocumentChunk)
            .where(*filters)
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(offset)
            .limit(size)
        )
        .all()
    )

    return DocumentChunkListResponse(
        items=list(chunks),
        total=total,
        page=page,
        size=size,
        pages=total_pages,
    )


@router.get("/{document_id}/download")
def download_document(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst", "viewer"])),
    db: Session = Depends(get_db),
):
    """Download the original stored document securely."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)

    file_path = storage_service.get_absolute_path(doc.storage_path or doc.storage_key)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored document file could not be located on disk",
        )

    # Safe filename for Content-Disposition header
    safe_filename = doc.original_filename or doc.file_name
    encoded_filename = urllib.parse.quote(safe_filename)

    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{document_id}/retry", response_model=DocumentStatusResponse)
def retry_document_processing(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor", "analyst"])),
    db: Session = Depends(get_db),
):
    """Retry processing a failed or uncompleted document."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)

    if doc.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is currently being processed. Please wait for completion.",
        )

    doc.status = "queued"
    doc.processing_error = None
    db.commit()

    background_tasks.add_task(_process_document_in_background, doc.id)

    return DocumentStatusResponse(
        document_id=doc.id,
        status="queued",
        processing_error=None,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        extracted_text_length=doc.extracted_text_length,
        processed_at=doc.processed_at,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    document_id: uuid.UUID,
    membership: OrganizationMember = Depends(require_roles(["owner", "admin", "auditor"])),
    db: Session = Depends(get_db),
):
    """Soft delete a document and invalidate access."""
    _get_audit_or_404(db, organization_id, audit_id)
    doc = _get_document_or_404(db, organization_id, audit_id, document_id)

    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return None

