from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import uuid


class ResourceBase(BaseModel):
    provider_resource_id: str
    name: Optional[str] = None
    region: str
    state: str
    tags: Optional[Dict[str, str]] = None
    instance_type: Optional[str] = None


class Resource(ResourceBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    cloud_account_id: uuid.UUID
    resource_type: str
    provider_type: Optional[str] = None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedResources(BaseModel):
    items: List[Resource]
    total: int
    page: int
    page_size: int
    total_pages: int


class ResourceFilter(BaseModel):
    """Filters for listing resources."""
    provider_type: Optional[str] = None
    state: Optional[str] = None
    cloud_account_id: Optional[uuid.UUID] = None
    region: Optional[str] = None
