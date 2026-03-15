from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import uuid


class PricingJobRunResponse(BaseModel):
    id: uuid.UUID
    provider_type: str
    status: str
    trigger: str
    regions_requested: Optional[int] = None
    records_updated: Optional[int] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class ProviderStatus(BaseModel):
    last_run: Optional[PricingJobRunResponse] = None
    status: str  # "success", "failed", "running", "never_run"


class PricingStatusSummary(BaseModel):
    next_scheduled_utc: Optional[str] = None
    is_running: bool
    providers: Dict[str, ProviderStatus]


class PricingJobTriggerRequest(BaseModel):
    provider_type: Optional[str] = None
    gcp_pricing_account_id: Optional[uuid.UUID] = None


class PricingJobTriggerResponse(BaseModel):
    job_ids: List[uuid.UUID]
    message: str


class GcpAccountOption(BaseModel):
    id: uuid.UUID
    name: str
    project_id: Optional[str] = None

    class Config:
        from_attributes = True
