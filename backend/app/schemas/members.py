from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MemberAddRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern="^(admin|auditor|analyst|viewer)$")


class MemberRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(owner|admin|auditor|analyst|viewer)$")


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    role: str
    created_at: datetime
