from app.database.models.identity import (
    Organization,
    User,
    OrganizationMember,
)
from app.database.models.auth import (
    RefreshToken,
)
from app.database.models.audits import (
    Audit,
    AuditRun,
)
from app.database.models.documents import (
    AuditDocument,
    DocumentChunk,
)
from app.database.models.regulatory import (
    RegulatoryFramework,
    RegulatoryDocument,
    RegulatoryDocumentChunk,
    RequirementSource,
    AuditRequirement,
    RequirementAuditHistory,
    RegulatoryExtractionJob,
)
from app.database.models.assessments import (
    Requirement,
    Threat,
    ControlAssessment,
)
from app.database.models.threats import (
    ThreatAnalysisRun,
    DiscoveredAsset,
    AttackSurface,
    AttackPathNode,
    ThreatAsset,
    ThreatRequirementMapping,
    ThreatAuditHistory,
    ThreatEvidenceReference,
)
from app.database.models.defence import (
    DefenceAnalysisRun,
    DiscoveredControl,
    ControlRequirementMapping,
    ControlThreatMapping,
    ControlEvidenceReference,
    ControlAuditHistory,
    FindingControl,
    FindingAuditHistory,
)
from app.database.models.findings import (
    Finding,
    EvidenceReference,
    FindingRequirement,
    FindingThreat,
)
from app.database.models.agents import (
    AgentRun,
    AgentEvent,
    AgentOutput,
)
from app.database.models.adjudication import (
    AdjudicationQuestion,
    AdjudicationAnswer,
    AdjudicationRun,
    AdjudicationDecision,
    AdjudicationSource,
    AdjudicationContradiction,
    AdjudicationAuditHistory,
)
from app.database.models.reports import (
    Report,
)

__all__ = [
    # Identity & Tenancy
    "Organization",
    "User",
    "OrganizationMember",
    "RefreshToken",
    # Audit Management
    "Audit",
    "AuditRun",
    # Document Management
    "AuditDocument",
    "DocumentChunk",
    # Regulatory Knowledge Base
    "RegulatoryFramework",
    "RegulatoryDocument",
    "RegulatoryDocumentChunk",
    "RequirementSource",
    "AuditRequirement",
    "RequirementAuditHistory",
    "RegulatoryExtractionJob",
    # Compliance & Threats
    "Requirement",
    "Threat",
    "ControlAssessment",
    # Adversarial Strategist Threat Modeling (Milestone 5)
    "ThreatAnalysisRun",
    "DiscoveredAsset",
    "AttackSurface",
    "AttackPathNode",
    "ThreatAsset",
    "ThreatRequirementMapping",
    "ThreatAuditHistory",
    "ThreatEvidenceReference",
    # Defence Auditor (Milestone 6)
    "DefenceAnalysisRun",
    "DiscoveredControl",
    "ControlRequirementMapping",
    "ControlThreatMapping",
    "ControlEvidenceReference",
    "ControlAuditHistory",
    "FindingControl",
    "FindingAuditHistory",
    # Findings & Evidence
    "Finding",
    "EvidenceReference",
    "FindingRequirement",
    "FindingThreat",
    # Agent Execution
    "AgentRun",
    "AgentEvent",
    "AgentOutput",
    # Adjudication & Consensus (Milestone 7)
    "AdjudicationQuestion",
    "AdjudicationAnswer",
    "AdjudicationRun",
    "AdjudicationDecision",
    "AdjudicationSource",
    "AdjudicationContradiction",
    "AdjudicationAuditHistory",
    # Reports
    "Report",
]

