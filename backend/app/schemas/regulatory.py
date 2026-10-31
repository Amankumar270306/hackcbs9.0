"""Pydantic schemas for Regulatory Knowledge Base, Legal Analyst, and Audit Mappings."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Frameworks
# -----------------------------------------------------------------------------

class RegulatoryFrameworkCreate(BaseModel):
    name: str = Field(..., max_length=255)
    short_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    issuing_authority: str = Field(..., max_length=255)
    jurisdiction: str = Field(default="Global", max_length=100)
    framework_type: str = Field(default="standard")
    official_source_url: Optional[str] = None
    version: str = Field(default="1.0", max_length=50)
    effective_date: Optional[datetime] = None
    framework_metadata: Dict[str, Any] = Field(default_factory=dict)


class RegulatoryFrameworkUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    issuing_authority: Optional[str] = None
    jurisdiction: Optional[str] = None
    framework_type: Optional[str] = None
    official_source_url: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[datetime] = None
    status: Optional[str] = None
    framework_metadata: Optional[Dict[str, Any]] = None


class RegulatoryFrameworkResponse(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    name: str
    short_name: str
    description: Optional[str] = None
    issuing_authority: str
    jurisdiction: str
    framework_type: str
    official_source_url: Optional[str] = None
    version: str
    effective_date: Optional[datetime] = None
    status: str
    framework_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Regulatory Documents & Chunks
# -----------------------------------------------------------------------------

class RegulatoryDocumentResponse(BaseModel):
    id: uuid.UUID
    framework_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    title: str
    document_number: Optional[str] = None
    version: str
    source_url: Optional[str] = None
    original_filename: str
    stored_filename: str
    storage_key: str
    file_extension: str
    file_size_bytes: int
    mime_type: str
    document_hash: str
    issuing_authority: Optional[str] = None
    status: str
    processing_error: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegulatoryDocumentChunkResponse(BaseModel):
    id: uuid.UUID
    regulatory_document_id: uuid.UUID
    chunk_index: int
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    token_count: Optional[int] = None
    character_count: int
    content: str
    start_char_offset: Optional[int] = None
    end_char_offset: Optional[int] = None
    chunk_metadata: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Extraction Jobs
# -----------------------------------------------------------------------------

class RegulatoryExtractionJobResponse(BaseModel):
    id: uuid.UUID
    regulatory_document_id: uuid.UUID
    status: str
    model_name: str
    prompt_version: str
    chunks_total: int
    chunks_processed: int
    requirements_extracted: int
    error_message: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Requirements, Sources, and Audit History
# -----------------------------------------------------------------------------

class RequirementSourceResponse(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    regulatory_document_id: uuid.UUID
    document_chunk_id: Optional[uuid.UUID] = None
    section_reference: Optional[str] = None
    page_number: Optional[int] = None
    exact_excerpt: str
    source_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequirementAuditHistoryResponse(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    reviewer_id: Optional[uuid.UUID] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    changes: Dict[str, Any]
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequirementResponse(BaseModel):
    id: uuid.UUID
    framework_id: Optional[uuid.UUID] = None
    regulatory_document_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    framework: str
    framework_version: Optional[str] = None
    identifier: str
    requirement_code: Optional[str] = None
    title: str
    description: str
    requirement_statement: Optional[str] = None
    detailed_description: Optional[str] = None
    obligation_type: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    applicability: str
    applicability_conditions: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_section: Optional[str] = None
    source_page: Optional[int] = None
    source_excerpt: Optional[str] = None
    source_chunk_id: Optional[uuid.UUID] = None
    confidence_score: Optional[float] = None
    extraction_status: str
    review_status: str
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    sources: Optional[List[RequirementSourceResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class RequirementListResponse(BaseModel):
    items: List[RequirementResponse]
    total: int
    limit: int
    offset: int


class RequirementEditRequest(BaseModel):
    title: Optional[str] = None
    requirement_statement: Optional[str] = None
    detailed_description: Optional[str] = None
    obligation_type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    applicability: Optional[str] = None
    applicability_conditions: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_section: Optional[str] = None
    reason: Optional[str] = None


class RequirementReviewActionRequest(BaseModel):
    reason: Optional[str] = None


# -----------------------------------------------------------------------------
# Audit Requirement Mapping & Evidence Suggestions
# -----------------------------------------------------------------------------

class AuditRequirementMapRequest(BaseModel):
    requirement_ids: List[uuid.UUID]


class AuditRequirementUpdateRequest(BaseModel):
    applicability_status: str
    applicability_reason: Optional[str] = None


class AuditRequirementResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    requirement_id: uuid.UUID
    applicability_status: str
    applicability_reason: Optional[str] = None
    added_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    requirement: Optional[RequirementResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AuditEvidenceSuggestionResponse(BaseModel):
    document_id: str
    filename: str
    relevance_score: float
    page_count: Optional[int] = None
    matched_keywords: List[str]
