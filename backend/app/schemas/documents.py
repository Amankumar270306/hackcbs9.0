"""Pydantic schemas for Document Management and Processing."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    audit_run_id: Optional[uuid.UUID] = None
    uploaded_by: Optional[uuid.UUID] = None

    original_filename: str
    stored_filename: Optional[str] = None
    file_extension: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    file_hash_sha256: str
    status: str
    processing_error: Optional[str] = None
    extracted_text_length: int = 0
    page_count: Optional[int] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="doc_metadata")
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    size: int
    pages: int
    total_file_size_bytes: int = 0


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    status: str
    processing_error: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: int = 0
    extracted_text_length: int = 0
    processed_at: Optional[datetime] = None


class DocumentTextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    original_filename: str
    extracted_text: Optional[str] = None
    extracted_text_length: int = 0
    page_count: Optional[int] = None


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    document_id: uuid.UUID
    audit_document_id: Optional[uuid.UUID] = None
    chunk_index: int
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    token_count: Optional[int] = None
    character_count: int = 0
    content: str
    start_char_offset: Optional[int] = None
    end_char_offset: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="chunk_metadata")
    created_at: datetime


class DocumentChunkListResponse(BaseModel):
    items: List[DocumentChunkResponse]
    total: int
    page: int
    size: int
    pages: int
