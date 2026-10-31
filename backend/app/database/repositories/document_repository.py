import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.documents import AuditDocument, DocumentChunk


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(
        self,
        organization_id: uuid.UUID,
        audit_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        file_name: str,
        file_size_bytes: int,
        mime_type: str,
        storage_path: str,
        checksum_sha256: str,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditDocument:
        doc = AuditDocument(
            organization_id=organization_id,
            audit_id=audit_id,
            audit_run_id=audit_run_id,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            storage_path=storage_path,
            checksum_sha256=checksum_sha256,
            doc_metadata=doc_metadata or {},
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def add_chunks(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks_data: List[Dict[str, Any]],
    ) -> List[DocumentChunk]:
        created_chunks = []
        for c in chunks_data:
            chunk = DocumentChunk(
                organization_id=organization_id,
                audit_run_id=audit_run_id,
                audit_document_id=document_id,
                chunk_index=c["chunk_index"],
                page_number=c.get("page_number"),
                content=c["content"],
                start_char_offset=c.get("start_char_offset"),
                end_char_offset=c.get("end_char_offset"),
                chunk_metadata=c.get("chunk_metadata", {}),
            )
            self.db.add(chunk)
            created_chunks.append(chunk)

        self.db.flush()
        return created_chunks

