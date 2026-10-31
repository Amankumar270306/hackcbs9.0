"""Pydantic schemas for Report Generator: Multi-Agent Audit Reports, Traceability & Previews."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Pre-flight Readiness Schemas
# ---------------------------------------------------------------------------

class ReadinessCheckItem(BaseModel):
    category: str
    label: str
    status: str = Field(..., description="ready, missing, warning, blocked")
    detail: str
    count: int = 0


class ReportReadinessCheck(BaseModel):
    audit_id: uuid.UUID
    is_ready: bool
    adjudication_runs_count: int = 0
    latest_adjudication_run_id: Optional[uuid.UUID] = None
    latest_adjudication_run_status: Optional[str] = None
    total_decisions_count: int = 0
    stale_decisions_count: int = 0
    unresolved_contradictions_count: int = 0
    pending_human_reviews_count: int = 0
    documents_count: int = 0
    chunks_count: int = 0
    checks: List[ReadinessCheckItem] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report Creation & Configuration
# ---------------------------------------------------------------------------

class ReportCreateRequest(BaseModel):
    adjudication_run_id: Optional[uuid.UUID] = Field(
        None,
        description="Optional target adjudication run ID. Defaults to the latest completed adjudication run.",
    )
    title: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional custom title for the report. Defaults to auto-generated title.",
    )
    format: str = Field(
        "pdf",
        description="Desired report format: 'pdf', 'html', 'json', 'markdown'",
    )


# ---------------------------------------------------------------------------
# Structured Report Section Data Models (Sections 1 to 12)
# ---------------------------------------------------------------------------

class ReportCoverPageData(BaseModel):
    organization_name: str
    audit_name: str
    audit_id: str
    report_title: str
    report_id: str
    report_version: str
    generated_at: str
    target_system: str
    environment: str
    report_status: str
    framework_names: List[str] = Field(default_factory=list)


class ReportExecutiveSummaryData(BaseModel):
    narrative: str
    total_requirements_assessed: int = 0
    supported_requirements_count: int = 0
    partially_supported_count: int = 0
    nonconformance_count: int = 0
    total_controls_documented: int = 0
    total_threats_modeled: int = 0
    mitigated_threats_count: int = 0
    unmitigated_threats_count: int = 0
    total_findings_count: int = 0
    critical_findings_count: int = 0
    high_findings_count: int = 0
    unresolved_contradictions_count: int = 0
    pending_human_reviews_count: int = 0
    stale_decisions_count: int = 0
    average_confidence_score: float = 0.0
    evidence_limitations: List[str] = Field(default_factory=list)


class ReportScopeData(BaseModel):
    target_system: str
    environment: str
    audit_scope_description: Optional[str] = None
    uploaded_documents: List[Dict[str, Any]] = Field(default_factory=list)
    regulatory_frameworks: List[Dict[str, Any]] = Field(default_factory=list)
    agents_involved: List[Dict[str, str]] = Field(default_factory=list)
    methodology_overview: str
    data_limitations: List[str] = Field(default_factory=list)
    human_review_methodology: str


class ReportRequirementItem(BaseModel):
    requirement_id: str
    title: str
    statement: str
    framework_name: str
    obligation_type: str
    applicability_status: str
    adjudication_outcome: str
    confidence_score: float
    is_provisional: bool
    is_stale: bool = False
    human_review_status: str
    supporting_controls: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class ReportAssetItem(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    description: Optional[str] = None
    criticality: str
    trust_boundary: Optional[str] = None
    source_documents: List[str] = Field(default_factory=list)
    linked_threat_ids: List[str] = Field(default_factory=list)


class ReportAttackSurfaceItem(BaseModel):
    surface_id: str
    surface_name: str
    entry_point: str
    protocol: Optional[str] = None
    authentication_required: Optional[bool] = None
    trust_boundary: Optional[str] = None
    relevant_threat_count: int = 0


class ReportThreatItem(BaseModel):
    threat_id: str
    title: str
    description: str
    stride_category: str
    threat_category: Optional[str] = None
    affected_assets: List[str] = Field(default_factory=list)
    attack_surface: Optional[str] = None
    attack_path_summary: Optional[str] = None
    likelihood: int
    impact: int
    risk_score: int
    severity: str
    is_provisional: bool
    is_stale: bool = False
    adjudication_outcome: str
    mitigation_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    related_controls: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class ReportControlItem(BaseModel):
    control_id: str
    title: str
    control_description: str
    evidence_maturity: str
    implementation_status: str
    related_requirements: List[str] = Field(default_factory=list)
    related_threats: List[str] = Field(default_factory=list)
    assessment_outcome: Optional[str] = None
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    contradictory_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    human_review_status: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class ReportFindingItem(BaseModel):
    finding_id: str
    title: str
    description: str
    severity: str
    risk_score: int
    likelihood: int
    impact: int
    associated_requirements: List[str] = Field(default_factory=list)
    associated_threats: List[str] = Field(default_factory=list)
    associated_controls: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_corrective_action: Optional[str] = None
    review_status: str


class ReportContradictionItem(BaseModel):
    contradiction_id: str
    contradiction_type: str
    description: str
    claim_a: str
    claim_b: str
    severity: str
    resolution_status: str
    resolution_notes: Optional[str] = None
    sources_involved: List[str] = Field(default_factory=list)


class ReportRemediationItem(BaseModel):
    item_id: str
    priority: str = Field(..., description="Critical, High, Medium, Low")
    sequence: int
    related_finding_or_threat: str
    title: str
    recommended_action: str
    technical_rationale: str
    supporting_evidence_reference: Optional[str] = None


class ReportStructuredData(BaseModel):
    cover_page: ReportCoverPageData
    executive_summary: ReportExecutiveSummaryData
    scope_and_methodology: ReportScopeData
    regulatory_requirements: List[ReportRequirementItem] = Field(default_factory=list)
    discovered_assets: List[ReportAssetItem] = Field(default_factory=list)
    attack_surfaces: List[ReportAttackSurfaceItem] = Field(default_factory=list)
    threat_assessment: List[ReportThreatItem] = Field(default_factory=list)
    control_assessment: List[ReportControlItem] = Field(default_factory=list)
    findings_register: List[ReportFindingItem] = Field(default_factory=list)
    contradictions_and_gaps: List[ReportContradictionItem] = Field(default_factory=list)
    missing_evidence_list: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_roadmap: List[ReportRemediationItem] = Field(default_factory=list)
    limitations_and_disclaimers: List[str] = Field(default_factory=list)
    appendix: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API Responses
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    adjudication_run_id: Optional[uuid.UUID] = None
    audit_run_id: Optional[uuid.UUID] = None
    title: str
    version: int
    format: str
    generation_status: str
    storage_path: Optional[str] = None
    file_checksum: Optional[str] = None
    file_size: Optional[int] = None
    summary: Optional[str] = None
    is_stale: bool = False
    error_message: Optional[str] = None
    created_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    report_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int


class ReportStructuredPreviewResponse(BaseModel):
    report_id: uuid.UUID
    title: str
    version: int
    format: str
    generation_status: str
    created_at: datetime
    is_stale: bool
    data: ReportStructuredData

