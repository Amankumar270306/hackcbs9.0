from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    application_name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None


class AuditUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    application_name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    application_name: str
    description: Optional[str]
    status: str
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    runs_count: int = 0
    document_count: int = 0
    finding_count: int = 0
    latest_run: Optional[Dict[str, Any]] = None


class AuditListResponse(BaseModel):
    items: List[AuditResponse]
    total: int
    page: int
    size: int
