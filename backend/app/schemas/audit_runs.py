from datetime import datetime
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditRunCreate(BaseModel):
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    summary: Optional[str] = None


class AuditRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    audit_id: uuid.UUID
    run_number: int
    status: str
    risk_score: Optional[float]
    summary: Optional[str]
    config: Dict[str, Any]
    created_by: Optional[uuid.UUID]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
