"""Pydantic schemas for Adjudicator: Cross-Agent Consensus, Reconciliation, Contradictions & Human Review."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# LLM Extraction & Reasoning Schemas
# ---------------------------------------------------------------------------

class AdjudicationLLMCitation(BaseModel):
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    exact_excerpt: str = Field(..., description="Verbatim quotation from the document chunk")
    source_agent: str = Field("defence_auditor", description="legal_analyst, adversarial_strategist, defence_auditor, document_extractor")
    source_entity_type: str = Field("discovered_control", description="regulatory_requirement, threat_scenario, discovered_control, control_assessment, finding, document_chunk")
    source_entity_id: Optional[str] = None
    source_role: str = Field("supporting", description="supporting, contradictory, contextual, informational")


class AdjudicationLLMDecision(BaseModel):
    category: str = Field("requirement_compliance", description="requirement_compliance, threat_mitigation, control_effectiveness, cross_cutting")
    related_entity_type: str = Field("requirement", description="requirement, threat, control, general")
    related_entity_id: Optional[str] = None
    outcome_status: str = Field(..., description="Valid controlled outcome status")
    summary: str
    reasoning: str
    confidence_score: float = Field(0.85, ge=0.0, le=1.0)
    is_provisional: bool = False
    requires_human_review: bool = False
    evidence_limitations: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    supporting_sources: List[AdjudicationLLMCitation] = Field(default_factory=list)


class AdjudicationLLMContradiction(BaseModel):
    category: str = Field("requirement_vs_control", description="requirement_vs_control, threat_vs_control, contradictory_documents, ai_vs_human_review, cross_agent")
    title: str
    description: str
    conflicting_claims: List[Dict[str, Any]] = Field(default_factory=list)
    source_references: List[Dict[str, Any]] = Field(default_factory=list)
    impact: str
    severity: str = Field("medium", description="critical, high, medium, low")


class AdjudicatorOutput(BaseModel):
    decisions: List[AdjudicationLLMDecision] = Field(default_factory=list)
    contradictions: List[AdjudicationLLMContradiction] = Field(default_factory=list)
    adjudication_summary: Optional[str] = None
    missing_agent_limitations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------

class AdjudicationReadinessResponse(BaseModel):
    audit_id: uuid.UUID
    is_ready: bool
    requirements_count: int
    approved_requirements_count: int
    pending_requirements_count: int
    threats_count: int
    accepted_threats_count: int
    pending_threats_count: int
    controls_count: int
    assessments_count: int
    findings_count: int
    evidence_chunks_count: int
    readiness_notes: List[str]
    has_legal_analyst_data: bool
    has_adversarial_strategist_data: bool
    has_defence_auditor_data: bool


class AdjudicationRunCreateRequest(BaseModel):
    model_name: Optional[str] = "gemini-1.5-flash"


class AdjudicationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    status: str
    model_name: str
    prompt_version: str
    input_source_snapshot: Dict[str, Any]
    requirements_processed_count: int
    threats_processed_count: int
    controls_processed_count: int
    decisions_generated_count: int
    contradictions_detected_count: int
    execution_duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    execution_metrics: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AdjudicationSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_agent: str
    source_entity_type: str
    source_entity_id: uuid.UUID
    source_version: Optional[str] = None
    source_role: str
    citation_reference: Optional[str] = None
    exact_excerpt: Optional[str] = None
    chunk_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    is_citation_valid: bool
    citation_validation_notes: Optional[str] = None
    created_at: datetime


class AdjudicationAuditHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: Optional[str] = None
    action: str
    previous_status: Optional[str] = None
    new_status: str
    previous_content: Optional[Dict[str, Any]] = None
    updated_content: Optional[Dict[str, Any]] = None
    justification: str
    created_at: datetime


class AdjudicationDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    adjudication_run_id: uuid.UUID
    decision_category: str
    related_entity_type: str
    related_entity_id: Optional[uuid.UUID] = None
    outcome_status: str
    summary: str
    reasoning: str
    confidence_score: float
    is_provisional: bool
    requires_human_review: bool
    is_stale: bool
    evidence_limitations: Optional[str] = None
    assumptions: List[str]
    missing_information: List[str]
    recommended_action: Optional[str] = None
    review_status: str
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    decision_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    sources: List[AdjudicationSourceResponse] = Field(default_factory=list)


class AdjudicationDecisionDetailResponse(AdjudicationDecisionResponse):
    audit_history: List[AdjudicationAuditHistoryResponse] = Field(default_factory=list)


class AdjudicationContradictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    adjudication_run_id: uuid.UUID
    contradiction_category: str
    title: str
    description: str
    conflicting_claims: List[Dict[str, Any]]
    source_references: List[Dict[str, Any]]
    impact: str
    severity: str
    resolution_status: str
    resolution_notes: Optional[str] = None
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    audit_history: List[AdjudicationAuditHistoryResponse] = Field(default_factory=list)


class DecisionReviewActionRequest(BaseModel):
    action: str = Field(..., description="'approve', 'reject', 'more_info_requested', 'reassess'")
    justification: str = Field(..., min_length=3)


class DecisionEditRequest(BaseModel):
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    outcome_status: Optional[str] = None
    confidence_score: Optional[float] = None
    recommended_action: Optional[str] = None
    justification: str = Field(..., min_length=3)


class ContradictionResolveRequest(BaseModel):
    resolution_status: str = Field(..., description="'resolved', 'clarification_requested', 'dismissed', 'unresolved'")
    resolution_notes: str = Field(..., min_length=3)


class AdjudicationStaleStatusResponse(BaseModel):
    has_stale_decisions: bool
    stale_decisions_count: int
    latest_adjudication_completed_at: Optional[datetime] = None
    newer_source_changes_count: int
    stale_reasons: List[str] = Field(default_factory=list)

