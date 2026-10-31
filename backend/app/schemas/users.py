from datetime import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    created_at: datetime


class UserOrgMembershipDetail(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    organizations: List[UserOrgMembershipDetail]
