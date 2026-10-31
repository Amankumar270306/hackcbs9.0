"""Pydantic validation models for structured Legal Analyst LLM output."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.services.ai.prompt_manager import OBLIGATION_TYPES, STANDARD_CATEGORIES


class ExtractedRequirementItem(BaseModel):
    """Normalized atomic compliance requirement extracted from a regulatory chunk."""

    requirement_code: str = Field(..., description="Unique concise requirement identifier, e.g. REQ-01 or CC6.1")
    title: str = Field(..., description="Concise descriptive title of the obligation")
    requirement_statement: str = Field(..., description="Testable declarative statement specifying the exact obligation")
    detailed_description: Optional[str] = Field(None, description="Detailed explanatory context")
    obligation_type: str = Field(default="mandatory", description="Level of obligation")
    category: str = Field(default="Other", description="Standard compliance category")
    subcategory: Optional[str] = Field(None, description="Optional granular subcategory")
    applicability: str = Field(default="general", description="Applicability scope")
    applicability_conditions: Optional[str] = Field(None, description="Conditions trigger")
    jurisdiction: Optional[str] = Field(default="Global", description="Legal jurisdiction")
    source_section: Optional[str] = Field(None, description="Regulatory section heading or number")
    source_page: Optional[int] = Field(None, description="Page number where excerpt appears")
    source_excerpt: str = Field(..., description="Exact verbatim text quote from the source chunk")
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence between 0 and 1")

    @field_validator("obligation_type", mode="before")
    @classmethod
    def validate_obligation_type(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "mandatory"
        cleaned = v.strip().lower()
        if cleaned in OBLIGATION_TYPES:
            return cleaned
        if "shall" in cleaned or "must" in cleaned or "mandatory" in cleaned or "required" in cleaned:
            return "mandatory"
        if "should" in cleaned or "recommend" in cleaned:
            return "recommended"
        if "condition" in cleaned or "if" in cleaned:
            return "conditional"
        return "unclear"

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "Other"
        cleaned = v.strip()
        for cat in STANDARD_CATEGORIES:
            if cat.lower() == cleaned.lower():
                return cat
        # Fuzzy keyword matching if close
        cleaned_lower = cleaned.lower()
        if "access" in cleaned_lower or "iam" in cleaned_lower or "auth" in cleaned_lower:
            return "Identity and Access Management"
        if "encrypt" in cleaned_lower or "data protect" in cleaned_lower:
            return "Data Protection & Encryption"
        if "network" in cleaned_lower or "firewall" in cleaned_lower:
            return "Network Security"
        if "incident" in cleaned_lower or "breach" in cleaned_lower:
            return "Incident Response & Management"
        if "vulnerab" in cleaned_lower or "patch" in cleaned_lower:
            return "Vulnerability Management"
        if "log" in cleaned_lower or "audit" in cleaned_lower:
            return "Logging & Auditing"
        if "vendor" in cleaned_lower or "third-party" in cleaned_lower or "supply chain" in cleaned_lower:
            return "Third-Party & Vendor Risk"
        if "continuity" in cleaned_lower or "disaster" in cleaned_lower or "backup" in cleaned_lower:
            return "Business Continuity & Disaster Recovery"
        if "privacy" in cleaned_lower or "consent" in cleaned_lower or "gdpr" in cleaned_lower or "dpdp" in cleaned_lower:
            return "Privacy & Consent Management"
        if "crypto" in cleaned_lower or "key" in cleaned_lower:
            return "Cryptography & Key Management"
        if "cloud" in cleaned_lower or "virtual" in cleaned_lower:
            return "Cloud & Virtualization Security"
        return "Other"

    @field_validator("confidence_score", mode="before")
    @classmethod
    def validate_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.85


class GeminiExtractionResponse(BaseModel):
    """Full structured extraction payload parsed from Gemini response."""

    requirements: List[ExtractedRequirementItem] = Field(default_factory=list)
    document_summary: Optional[str] = None
    notes: Optional[str] = None

