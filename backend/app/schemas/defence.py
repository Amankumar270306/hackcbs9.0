"""Pydantic schemas for Defence Auditor agent, controls, assessments, findings, and human review."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# LLM Extraction Schemas
# ---------------------------------------------------------------------------

class ExtractedEvidenceCitationItem(BaseModel):
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    exact_excerpt: str = Field(..., description="Verbatim quotation from the document chunk")
    citation_type: str = Field("direct_evidence", description="direct_evidence, contradictory_evidence, contextual_evidence, inference, missing_evidence")
    evidence_maturity: str = Field("policy", description="policy, design, implementation, operational")
    relevance_explanation: Optional[str] = None


class ExtractedControlItem(BaseModel):
    control_code: str = Field(..., description="e.g. CTRL-001")
    name: str
    description: str
    category: str = Field(..., description="e.g. Access Control, Cryptography, Network Security, Logging")
    control_objective: str
    implementation_status: str = Field("documented", description="documented, partially_documented, undocumented, unknown")
    operational_status: str = Field("unverified", description="active, planned, unverified, unknown")
    evidence_maturity: str = Field("policy", description="policy, design, implementation, operational")
    confidence_score: float = Field(0.90, ge=0.0, le=1.0)
    requirement_ids: List[str] = Field(default_factory=list)
    threat_ids: List[str] = Field(default_factory=list)
    evidence_citations: List[ExtractedEvidenceCitationItem] = Field(default_factory=list)


class ExtractedAssessmentItem(BaseModel):
    control_code: str
    requirement_id: Optional[str] = None
    threat_id: Optional[str] = None
    status: str = Field(..., description="effective_documented_control, partially_supported_control, insufficient_evidence, contradictory_evidence, confirmed_weakness, not_applicable")
    evidence_maturity: Optional[str] = Field("policy", description="policy, design, implementation, operational")
    assessment_explanation: str
    evidence_limitations: Optional[str] = None
    missing_information: Optional[str] = None
    contradictions: Optional[str] = None
    recommended_next_steps: Optional[str] = None
    confidence_score: Optional[float] = Field(0.90, ge=0.0, le=1.0)


class ExtractedFindingItem(BaseModel):
    finding_code: str = Field(..., description="e.g. GAP-001")
    title: str
    description: str
    finding_category: str = Field("documentation_gap", description="documentation_gap, implementation_evidence_gap, operational_evidence_gap, control_weakness, contradictory_evidence, coverage_gap")
    severity: Optional[str] = Field(None, description="low, medium, high, very_high, critical (computed from likelihood * impact if null)")
    evidence_state: str = Field("confirmed_weakness", description="confirmed_weakness, insufficient_evidence, contradictory_evidence")
    likelihood_score: int = Field(3, ge=1, le=5)
    impact_score: int = Field(3, ge=1, le=5)
    is_provisional: bool = False
    confidence_score: Optional[float] = Field(0.85, ge=0.0, le=1.0)
    remediation_recommendation: Optional[str] = None
    related_control_codes: List[str] = Field(default_factory=list)
    related_requirement_ids: List[str] = Field(default_factory=list)
    related_threat_ids: List[str] = Field(default_factory=list)
    evidence_citations: List[ExtractedEvidenceCitationItem] = Field(default_factory=list)


class DefenceAuditorOutput(BaseModel):
    controls: List[ExtractedControlItem] = Field(default_factory=list)
    assessments: List[ExtractedAssessmentItem] = Field(default_factory=list)
    findings: List[ExtractedFindingItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------

class DefenceAnalysisRunCreateRequest(BaseModel):
    model_name: Optional[str] = None


class DefenceAnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    status: str
    model_name: str
    prompt_version: str
    input_document_ids: List[str]
    input_requirement_ids: List[str]
    input_threat_ids: List[str]
    controls_discovered_count: int
    assessments_count: int
    findings_count: int
    execution_duration_ms: Optional[int]
    error_message: Optional[str]
    execution_metrics: Dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ControlEvidenceReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    assessment_id: Optional[uuid.UUID] = None
    audit_document_id: uuid.UUID
    document_chunk_id: Optional[uuid.UUID] = None
    original_filename: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    exact_excerpt: str
    citation_type: str
    evidence_maturity: str
    relevance_explanation: Optional[str] = None
    created_at: datetime


class ControlRequirementMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    requirement_id: uuid.UUID
    coverage_level: str
    mapping_rationale: Optional[str] = None
    confidence_score: float
    review_status: str
    requirement_identifier: Optional[str] = None
    requirement_statement: Optional[str] = None


class ControlThreatMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    threat_id: uuid.UUID
    mitigation_level: str
    mapping_rationale: Optional[str] = None
    confidence_score: float
    review_status: str
    threat_title: Optional[str] = None
    threat_severity: Optional[str] = None


class ControlAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: Optional[uuid.UUID] = None
    control_id: Optional[uuid.UUID] = None
    requirement_id: Optional[uuid.UUID] = None
    threat_id: Optional[uuid.UUID] = None
    defence_analysis_run_id: Optional[uuid.UUID] = None
    status: str
    assessment_explanation: Optional[str] = None
    evidence_maturity: Optional[str] = None
    evidence_limitations: Optional[str] = None
    missing_information: Optional[str] = None
    contradictions: Optional[str] = None
    recommended_next_steps: Optional[str] = None
    confidence_score: Optional[float] = None
    review_status: str
    review_reason: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ControlAuditHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    assessment_id: Optional[uuid.UUID] = None
    reviewer_id: Optional[uuid.UUID] = None
    reviewer_email: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    changes: Dict[str, Any]
    reason: Optional[str] = None
    created_at: datetime


class DiscoveredControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    defence_analysis_run_id: Optional[uuid.UUID] = None
    control_code: str
    name: str
    description: str
    category: str
    control_objective: str
    implementation_status: str
    operational_status: str
    evidence_maturity: str
    confidence_score: float
    created_at: datetime
    updated_at: datetime
    assessment_status: Optional[str] = None
    assessment_explanation: Optional[str] = None
    requirement_count: int = 0
    threat_count: int = 0
    evidence_count: int = 0


class ControlDetailResponse(DiscoveredControlResponse):
    assessments: List[ControlAssessmentResponse] = Field(default_factory=list)
    requirement_mappings: List[ControlRequirementMappingResponse] = Field(default_factory=list)
    threat_mappings: List[ControlThreatMappingResponse] = Field(default_factory=list)
    evidence_references: List[ControlEvidenceReferenceResponse] = Field(default_factory=list)
    audit_history: List[ControlAuditHistoryResponse] = Field(default_factory=list)


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: Optional[uuid.UUID] = None
    defence_analysis_run_id: Optional[uuid.UUID] = None
    finding_code: str
    title: str
    description: str
    severity: str
    evidence_state: str
    finding_category: Optional[str] = None
    likelihood_score: Optional[int] = None
    impact_score: Optional[int] = None
    risk_score: Optional[int] = None
    is_provisional: bool = False
    confidence_score: Optional[float] = None
    remediation_recommendation: Optional[str] = None
    review_status: str
    review_reason: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    related_control_codes: List[str] = Field(default_factory=list)


class FindingAuditHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    reviewer_id: Optional[uuid.UUID] = None
    reviewer_email: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    changes: Dict[str, Any]
    reason: Optional[str] = None
    created_at: datetime


class FindingDetailResponse(FindingResponse):
    related_controls: List[DiscoveredControlResponse] = Field(default_factory=list)
    audit_history: List[FindingAuditHistoryResponse] = Field(default_factory=list)


class DefenceReadinessResponse(BaseModel):
    is_ready: bool
    total_documents: int
    approved_requirements: int
    accepted_threats: int
    pending_threats: int
    rejected_threats: int
    blockers: List[str]
    warnings: List[str]


# ---------------------------------------------------------------------------
# Human Review Action Schemas
# ---------------------------------------------------------------------------

class ControlReviewActionRequest(BaseModel):
    action: str = Field(..., description="approve, reject, request_more_information, reassess")
    reason: Optional[str] = Field(None, description="Mandatory when action is reject")


class ControlEditRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    implementation_status: Optional[str] = None
    operational_status: Optional[str] = None
    evidence_maturity: Optional[str] = None
    assessment_status: Optional[str] = None
    assessment_explanation: Optional[str] = None
    reason: Optional[str] = None


class FindingReviewActionRequest(BaseModel):
    action: str = Field(..., description="approve, reject, request_more_information, reassess")
    reason: Optional[str] = Field(None, description="Mandatory when action is reject")


class FindingEditRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    finding_category: Optional[str] = None
    likelihood_score: Optional[int] = Field(None, ge=1, le=5)
    impact_score: Optional[int] = Field(None, ge=1, le=5)
    remediation_recommendation: Optional[str] = None
    reason: Optional[str] = None

