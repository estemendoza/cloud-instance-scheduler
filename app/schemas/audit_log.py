from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    event_type: str
    user_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    status_code: Optional[int] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True
