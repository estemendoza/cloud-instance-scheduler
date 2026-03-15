from pydantic import BaseModel
from typing import Optional


class ResourceSavings(BaseModel):
    """Estimated savings for a single resource."""
    resource_id: str
    instance_type: str
    hourly_rate: float
    stopped_hours_per_week: float
    monthly_savings: float
    annual_savings: float
    currency: str
    policy_name: Optional[str] = None
    note: Optional[str] = None


class OrganizationSavings(BaseModel):
    """Aggregated savings for an organization."""
    total_monthly_savings: float
    total_annual_savings: float
    currency: str
    resources_with_savings: int
    total_resources: int
