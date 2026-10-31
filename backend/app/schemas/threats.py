"""Pydantic validation and API schemas for Adversarial Threat Modeling (Milestone 5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# LLM Extraction & Validation Schemas
# ============================================================================

class SourceReferenceItem(BaseModel):
    """Source evidence citation reference."""
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    original_filename: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    exact_excerpt: str = Field(..., description="Verbatim quote from source evidence document")
    evidence_classification: str = Field(default="documented_fact")
    relevance_explanation: Optional[str] = None

    @field_validator("evidence_classification", mode="before")
    @classmethod
    def validate_classification(cls, v: Any) -> str:
        valid = {"documented_fact", "inference", "unknown", "contradictory_information"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "documented_fact"


class ExtractedAssetItem(BaseModel):
    """System asset discovered by Adversarial Strategist."""
    name: str = Field(..., description="Asset name")
    asset_category: str = Field(default="data_store")
    description: str = Field(..., description="Description of the asset and role")
    sensitivity: str = Field(default="unknown")
    criticality: str = Field(default="unknown")
    data_classification: Optional[str] = None
    owner: str = Field(default="Unknown")
    relevant_component: Optional[str] = None
    evidence_classification: str = Field(default="documented_fact")
    confidence_score: float = Field(default=0.90, ge=0.0, le=1.0)
    source_references: List[SourceReferenceItem] = Field(default_factory=list)

    @field_validator("sensitivity", mode="before")
    @classmethod
    def validate_sensitivity(cls, v: Any) -> str:
        valid = {"public", "internal", "confidential", "restricted", "unknown"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "unknown"

    @field_validator("criticality", mode="before")
    @classmethod
    def validate_criticality(cls, v: Any) -> str:
        valid = {"low", "medium", "high", "critical", "unknown"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "unknown"


class ExtractedAttackSurfaceItem(BaseModel):
    """Attack surface entry point identified by Adversarial Strategist."""
    name: str = Field(..., description="Surface name")
    surface_type: str = Field(default="public_api")
    description: str = Field(..., description="Detailed description")
    exposed_component: Optional[str] = None
    access_requirements: str = Field(default="unknown")
    trust_boundary: str = Field(default="unknown")
    evidence_classification: str = Field(default="documented_fact")
    confidence_score: float = Field(default=0.90, ge=0.0, le=1.0)
    associated_assets: List[str] = Field(default_factory=list)
    source_references: List[SourceReferenceItem] = Field(default_factory=list)


class AttackPathNodeItem(BaseModel):
    """Node in an attack path / tree."""
    node_id: str = Field(..., description="Identifier like NODE-1")
    parent_node_id: Optional[str] = None
    node_type: str = Field(default="attack_step")
    description: str = Field(..., description="Description of attack step or condition")
    logical_operator: Optional[str] = None
    sequence_number: int = Field(default=1)
    supporting_references: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("node_type", mode="before")
    @classmethod
    def validate_node_type(cls, v: Any) -> str:
        valid = {"root_objective", "attack_step", "precondition", "exploit_action"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "attack_step"

    @field_validator("logical_operator", mode="before")
    @classmethod
    def validate_operator(cls, v: Any) -> Optional[str]:
        if not v:
            return None
        upper = str(v).upper().strip()
        if upper in {"AND", "OR"}:
            return upper
        return None


class MappedRequirementItem(BaseModel):
    """Mapping from threat to approved regulatory requirement."""
    requirement_code: str = Field(..., description="Approved requirement code (e.g. REQ-01)")
    relationship_type: str = Field(default="directly_related")
    rationale: Optional[str] = None
    confidence_score: float = Field(default=0.90, ge=0.0, le=1.0)

    @field_validator("relationship_type", mode="before")
    @classmethod
    def validate_rel_type(cls, v: Any) -> str:
        valid = {"directly_related", "indirectly_related", "potential_coverage", "requires_review"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "directly_related"


class GeneratedThreatItem(BaseModel):
    """Complete structured threat scenario generated by Adversarial Strategist."""
    threat_title: str = Field(..., description="Descriptive title")
    threat_description: str = Field(..., description="Comprehensive explanation")
    stride_category: str = Field(default="Information Disclosure")
    attack_objective: Optional[str] = None
    attack_vector: Optional[str] = None
    entry_point: Optional[str] = None
    preconditions: Optional[str] = None
    attack_steps: List[str] = Field(default_factory=list)
    target_assets: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    trust_boundaries_crossed: List[str] = Field(default_factory=list)
    potential_consequences: Optional[str] = None
    cia_confidentiality: str = Field(default="unknown")
    cia_integrity: str = Field(default="unknown")
    cia_availability: str = Field(default="unknown")
    likelihood_score: int = Field(default=3, ge=1, le=5)
    likelihood_rationale: Optional[str] = None
    impact_score: int = Field(default=3, ge=1, le=5)
    impact_rationale: Optional[str] = None
    is_provisional: bool = Field(default=False)
    confidence_score: float = Field(default=0.90, ge=0.0, le=1.0)
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    attack_path: List[AttackPathNodeItem] = Field(default_factory=list)
    source_references: List[SourceReferenceItem] = Field(default_factory=list)
    mapped_requirements: List[MappedRequirementItem] = Field(default_factory=list)

    @field_validator("stride_category", mode="before")
    @classmethod
    def validate_stride(cls, v: Any) -> str:
        valid = {
            "spoofing": "Spoofing",
            "tampering": "Tampering",
            "repudiation": "Repudiation",
            "information disclosure": "Information Disclosure",
            "denial of service": "Denial of Service",
            "elevation of privilege": "Elevation of Privilege",
        }
        if v and str(v).lower() in valid:
            return valid[str(v).lower()]
        return "Information Disclosure"

    @field_validator("cia_confidentiality", "cia_integrity", "cia_availability", mode="before")
    @classmethod
    def validate_cia(cls, v: Any) -> str:
        valid = {"none", "low", "medium", "high", "critical", "unknown"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "unknown"

    @field_validator("likelihood_score", "impact_score", mode="before")
    @classmethod
    def validate_score(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(1, min(5, val))
        except (ValueError, TypeError):
            return 3


class AdversarialStrategistOutput(BaseModel):
    """Full structured output returned from Gemini LLM for threat modeling."""
    assets: List[ExtractedAssetItem] = Field(default_factory=list)
    attack_surfaces: List[ExtractedAttackSurfaceItem] = Field(default_factory=list)
    threats: List[GeneratedThreatItem] = Field(default_factory=list)
    analysis_summary: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


# ============================================================================
# API Request & Response Schemas
# ============================================================================

class ThreatAnalysisTriggerRequest(BaseModel):
    """Request to initiate a new threat analysis run."""
    document_ids: Optional[List[UUID]] = None
    requirement_ids: Optional[List[UUID]] = None
    model_name: Optional[str] = None
    run_in_background: Optional[bool] = False


class ThreatAnalysisRunResponse(BaseModel):
    """Response containing threat analysis run status and summary."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    audit_id: UUID
    status: str
    model_name: str
    prompt_version: str
    input_document_ids: List[str]
    input_requirement_ids: List[str]
    assets_discovered_count: int
    attack_surfaces_count: int
    threats_generated_count: int
    execution_duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    execution_metrics: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DiscoveredAssetResponse(BaseModel):
    """Response schema for discovered asset."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    audit_id: UUID
    threat_analysis_run_id: Optional[UUID] = None
    name: str
    asset_category: str
    description: str
    sensitivity: str
    criticality: str
    data_classification: Optional[str] = None
    owner: str
    relevant_component: Optional[str] = None
    evidence_classification: str
    confidence_score: float
    source_references: List[Dict[str, Any]]
    asset_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AttackSurfaceResponse(BaseModel):
    """Response schema for attack surface."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    audit_id: UUID
    threat_analysis_run_id: Optional[UUID] = None
    name: str
    surface_type: str
    description: str
    exposed_component: Optional[str] = None
    access_requirements: str
    trust_boundary: str
    evidence_classification: str
    confidence_score: float
    associated_assets: List[str]
    source_references: List[Dict[str, Any]]
    surface_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AttackPathNodeResponse(BaseModel):
    """Response schema for an attack path node in the attack tree."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    threat_id: UUID
    node_id: str
    parent_node_id: Optional[str] = None
    node_type: str
    description: str
    logical_operator: Optional[str] = None
    sequence_number: int
    supporting_references: List[Dict[str, Any]]
    created_at: datetime


class ThreatEvidenceResponse(BaseModel):
    """Response schema for threat evidence reference."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    threat_id: UUID
    audit_document_id: UUID
    document_chunk_id: Optional[UUID] = None
    original_filename: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    exact_excerpt: str
    evidence_classification: str
    relevance_explanation: Optional[str] = None
    created_at: datetime


class ThreatRequirementMappingResponse(BaseModel):
    """Response schema for threat-to-regulatory-requirement mapping."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    threat_id: UUID
    requirement_id: UUID
    relationship_type: str
    rationale: Optional[str] = None
    confidence_score: float
    created_at: datetime

    # Denormalized / enriched fields for frontend display
    requirement_code: Optional[str] = None
    requirement_title: Optional[str] = None
    category: Optional[str] = None
    framework_name: Optional[str] = None


class ThreatAuditHistoryResponse(BaseModel):
    """Response schema for threat audit history trail."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    threat_id: UUID
    reviewer_id: Optional[UUID] = None
    reviewer_name: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    changes: Dict[str, Any]
    reason: Optional[str] = None
    created_at: datetime


class ThreatResponse(BaseModel):
    """Compact summary response for threat inventory lists."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audit_id: Optional[UUID] = None
    threat_analysis_run_id: Optional[UUID] = None
    threat_title: str
    threat_description: str
    stride_category: str
    threat_category: str
    attack_objective: Optional[str] = None
    attack_vector: Optional[str] = None
    entry_point: Optional[str] = None
    cia_confidentiality: str
    cia_integrity: str
    cia_availability: str
    likelihood_score: int
    impact_score: int
    risk_score: int
    severity: str
    is_provisional: bool
    confidence_score: float
    review_status: str
    review_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    mapped_requirements_count: int = 0
    attack_nodes_count: int = 0
    created_at: datetime
    updated_at: datetime


class ThreatDetailResponse(ThreatResponse):
    """Detailed response for single threat view with attack path, evidence, and mappings."""
    preconditions: Optional[str] = None
    attack_steps: List[str] = Field(default_factory=list)
    target_assets: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    trust_boundaries_crossed: List[str] = Field(default_factory=list)
    potential_consequences: Optional[str] = None
    likelihood_rationale: Optional[str] = None
    impact_rationale: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    threat_metadata: Dict[str, Any] = Field(default_factory=dict)
    attack_path_nodes: List[AttackPathNodeResponse] = Field(default_factory=list)
    evidence_references: List[ThreatEvidenceResponse] = Field(default_factory=list)
    requirement_mappings: List[ThreatRequirementMappingResponse] = Field(default_factory=list)
    audit_history: List[ThreatAuditHistoryResponse] = Field(default_factory=list)


class ThreatListResponse(BaseModel):
    """Paginated list of threats."""
    threats: List[ThreatResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class ThreatReviewActionRequest(BaseModel):
    """Action payload for human review (accept, reject, request_review)."""
    action: str = Field(..., description="'accept', 'reject', or 'request_review'")
    reason: Optional[str] = Field(None, description="Detailed reason for the review decision")

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: Any) -> str:
        valid = {"accept", "reject", "request_review"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        raise ValueError(f"Invalid review action: '{v}'. Must be one of {valid}")


class ThreatEditRequest(BaseModel):
    """Payload for human auditor editing a threat."""
    threat_title: Optional[str] = None
    threat_description: Optional[str] = None
    stride_category: Optional[str] = None
    attack_objective: Optional[str] = None
    attack_vector: Optional[str] = None
    entry_point: Optional[str] = None
    preconditions: Optional[str] = None
    attack_steps: Optional[List[str]] = None
    likelihood_score: Optional[int] = Field(None, ge=1, le=5)
    likelihood_rationale: Optional[str] = None
    impact_score: Optional[int] = Field(None, ge=1, le=5)
    impact_rationale: Optional[str] = None
    cia_confidentiality: Optional[str] = None
    cia_integrity: Optional[str] = None
    cia_availability: Optional[str] = None
    assumptions: Optional[List[str]] = None
    missing_information: Optional[List[str]] = None
    is_provisional: Optional[bool] = None
    reason: Optional[str] = Field(None, description="Auditor justification for the edits")


class ThreatAnalysisReadinessResponse(BaseModel):
    """Audit readiness pre-flight check for threat analysis."""
    audit_id: UUID
    audit_title: str
    is_ready: bool
    approved_requirements_count: int
    pending_requirements_count: int
    documents_count: int
    chunks_count: int
    previous_runs_count: int
    validation_messages: List[str]

