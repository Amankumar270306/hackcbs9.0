"""Document processing pipeline for Compliance Sentinel.

Coordinates upload validation (magic bytes, size, SHA-256 duplicate detection),
file persistence, format extraction (PDF/DOCX), deterministic chunk generation,
and transactional chunk persistence into YugabyteDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import zipfile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.audits import Audit
from app.database.models.documents import AuditDocument, DocumentChunk
from app.services.document_chunker import ChunkData, document_chunker
from app.services.document_storage import storage_service
from app.services.docx_extractor import docx_extractor
from app.services.pdf_extractor import DocumentExtractionError, pdf_extractor

logger = logging.getLogger("document_processor")


class DocumentValidationError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(status_code=status_code, detail=detail)


class DocumentProcessorService:
    PDF_MAGIC = b"%PDF-"
    ZIP_MAGIC = b"PK\x03\x04"

    @classmethod
    def validate_file_content(cls, header: bytes, filename: str) -> str:
        """Validate actual file contents via magic bytes rather than trusting filename or Content-Type.

        Returns detected extension: 'pdf' or 'docx'.
        """
        lower_name = filename.lower()

        if header.startswith(cls.PDF_MAGIC):
            if not lower_name.endswith(".pdf"):
                raise DocumentValidationError("File content is a PDF, but extension does not match .pdf")
            return "pdf"

        if header.startswith(cls.ZIP_MAGIC):
            # Verify it is indeed an Office Open XML / DOCX document
            try:
                with zipfile.ZipFile(io.BytesIO(header)) as z:
                    names = z.namelist()
                    if "[Content_Types].xml" not in names and "word/document.xml" not in names:
                        raise DocumentValidationError("ZIP archive is not a valid DOCX document")
            except zipfile.BadZipFile:
                # Bounded header might not have full central directory; test extension and magic
                pass

            if not lower_name.endswith(".docx"):
                raise DocumentValidationError("File content is a DOCX document, but extension does not match .docx")
            return "docx"

        raise DocumentValidationError(
            "Unsupported file format. Only valid PDF and DOCX files are supported."
        )

    @classmethod
    async def inspect_and_read_upload(
        cls, file: UploadFile, max_bytes: int = settings.MAX_UPLOAD_SIZE_BYTES
    ) -> Tuple[bytes, str, str, int]:
        """Stream/read upload with bounded memory, calculate SHA-256, validate magic bytes.

        Returns: (file_bytes, sha256_hash, file_extension, file_size_bytes)
        """
        filename = file.filename or "uploaded_file"
        hasher = hashlib.sha256()
        buffer = bytearray()
        total_size = 0

        # Read in 64 KB chunks
        chunk_size = 64 * 1024
        header_bytes = b""

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > max_bytes:
                raise DocumentValidationError(
                    f"File exceeds maximum allowed upload size of {max_bytes // (1024 * 1024)} MB",
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

            hasher.update(chunk)
            buffer.extend(chunk)

            if len(header_bytes) < 4096:
                header_bytes += chunk[: 4096 - len(header_bytes)]

        if total_size == 0:
            raise DocumentValidationError("Uploaded file is empty (0 bytes)")

        # Validate magic bytes against header
        file_extension = cls.validate_file_content(header_bytes, filename)
        sha256_hex = hasher.hexdigest()

        return bytes(buffer), sha256_hex, file_extension, total_size

    @classmethod
    def check_duplicate(cls, db: Session, audit_id: uuid.UUID, file_hash_sha256: str) -> None:
        """Reject duplicate upload within the same audit if an active document exists."""
        existing = db.execute(
            select(AuditDocument).where(
                AuditDocument.audit_id == audit_id,
                AuditDocument.checksum_sha256 == file_hash_sha256,
                AuditDocument.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

        if existing:
            raise DocumentValidationError(
                f"A document with identical content already exists in this audit: '{existing.file_name}' (ID: {existing.id})",
                status_code=status.HTTP_409_CONFLICT,
            )

    @classmethod
    def process_document_pipeline(cls, db: Session, document_id: uuid.UUID) -> None:
        """Synchronous or background task processing of a stored document.

        Extracts content, computes chunks, and persists them transactionally.
        """
        doc = db.get(AuditDocument, document_id)
        if not doc or doc.deleted_at is not None:
            logger.warning(f"Document {document_id} not found or deleted before processing")
            return

        # Atomically transition to 'processing'
        if doc.status == "processing":
            logger.info(f"Document {document_id} is already processing; skipping redundant trigger")
            return

        doc.status = "processing"
        doc.processing_error = None
        db.commit()

        try:
            # 1. Resolve stored file path
            file_path = storage_service.get_absolute_path(doc.storage_path or doc.storage_key)
            if not file_path.is_file():
                raise DocumentExtractionError(f"Stored file not found on disk at: {file_path}")

            extracted_text = ""
            page_count: Optional[int] = None
            chunks_data: List[ChunkData] = []
            extra_metadata: Dict[str, Any] = {}

            # 2. Extract and chunk based on extension
            ext = (doc.file_extension or "").lower().strip(".")
            if not ext and "." in doc.file_name:
                ext = doc.file_name.rsplit(".", 1)[-1].lower()

            if ext == "pdf":
                pdf_res = pdf_extractor.extract_from_file(file_path)
                extracted_text = pdf_res.text
                page_count = pdf_res.page_count
                extra_metadata.update(pdf_res.metadata)
                chunks_data = document_chunker.chunk_pdf(pdf_res)

            elif ext == "docx":
                docx_res = docx_extractor.extract_from_file(file_path)
                extracted_text = docx_res.text
                page_count = None  # Explicitly None for DOCX
                extra_metadata.update(docx_res.metadata)
                chunks_data = document_chunker.chunk_docx(docx_res)

            else:
                raise DocumentExtractionError(f"Unsupported file extension: .{ext}")

            # 3. Transactionally store chunks and update document metadata
            # Clear any preexisting chunks (for retries)
            db.execute(delete(DocumentChunk).where(DocumentChunk.audit_document_id == doc.id))

            for cd in chunks_data:
                chunk = DocumentChunk(
                    organization_id=doc.organization_id,
                    audit_id=doc.audit_id,
                    audit_run_id=doc.audit_run_id,
                    audit_document_id=doc.id,
                    chunk_index=cd.chunk_index,
                    page_number=cd.page_number,
                    page_start=cd.page_start,
                    page_end=cd.page_end,
                    section_title=cd.section_title,
                    token_count=cd.token_count,
                    character_count=cd.character_count,
                    content=cd.content,
                    start_char_offset=cd.start_char_offset,
                    end_char_offset=cd.end_char_offset,
                    chunk_metadata=cd.chunk_metadata,
                )
                db.add(chunk)

            # Update document record
            doc.extracted_text = extracted_text
            doc.extracted_text_length = len(extracted_text)
            doc.page_count = page_count
            doc.chunk_count = len(chunks_data)
            doc.status = "completed"
            doc.processed_at = datetime.now(timezone.utc)
            doc.processing_error = None

            # Merge metadata
            current_meta = dict(doc.doc_metadata or {})
            current_meta.update(extra_metadata)
            doc.doc_metadata = current_meta

            db.commit()
            logger.info(f"Successfully processed document {doc.id} ({doc.chunk_count} chunks, {doc.extracted_text_length} chars)")

        except Exception as exc:
            db.rollback()
            logger.error(f"Failed processing document {document_id}: {exc}", exc_info=True)
            # Re-fetch document and record failure
            doc = db.get(AuditDocument, document_id)
            if doc:
                doc.status = "failed"
                doc.processing_error = str(exc)
                doc.processed_at = datetime.now(timezone.utc)
                db.commit()


document_processor = DocumentProcessorService()

