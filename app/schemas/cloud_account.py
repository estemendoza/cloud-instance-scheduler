from pydantic import BaseModel, field_validator
from typing import Optional, Dict, List
from datetime import datetime
import uuid

from app.providers import get_valid_provider_types


class CloudAccountBase(BaseModel):
    name: str
    provider_type: str

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str) -> str:
        valid = get_valid_provider_types()
        if v not in valid:
            raise ValueError(
                f"Unsupported provider type: {v}. "
                f"Valid types: {', '.join(valid)}"
            )
        return v
    is_active: bool = True
    selected_regions: Optional[List[str]] = None  # null = scan all regions


class CloudAccountCreate(CloudAccountBase):
    credentials: Dict  # Provider-specific credentials (will be encrypted)


class CloudAccountUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    credentials: Optional[Dict] = None
    selected_regions: Optional[List[str]] = None


class CloudAccount(CloudAccountBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    credential_hints: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


class SyncResult(BaseModel):
    """Result of a resource sync operation."""
    created: int
    updated: int
    total: int
    accounts_synced: Optional[int] = None
