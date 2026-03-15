from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class OverrideBase(BaseModel):
    resource_id: uuid.UUID
    desired_state: str = Field(..., pattern="^(RUNNING|STOPPED)$")
    expires_at: datetime
    reason: Optional[str] = None


class OverrideCreate(OverrideBase):
    pass


class Override(OverrideBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
