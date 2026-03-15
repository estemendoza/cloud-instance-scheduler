from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class InstanceTypeInfo(BaseModel):
    """Instance type with pricing info."""
    instance_type: str
    hourly_rate: float
    region: str


class EstimateRequest(BaseModel):
    """Request for simple cost estimation."""
    provider: str = "aws"
    region: str
    instance_type: str
    hours_per_day: float = Field(ge=0, le=24)
    days_per_week: int = Field(ge=1, le=7)


class EstimateResponse(BaseModel):
    """Response for cost estimation."""
    instance_type: str
    region: str
    hourly_rate: float
    hours_per_day: float
    days_per_week: int
    daily_cost: float
    weekly_cost: float
    monthly_cost: float
    annual_cost: float
    currency: str = "USD"
    error: Optional[str] = None


class CompareInstanceRequest(BaseModel):
    """Single instance in comparison request."""
    provider: str = "aws"
    region: str
    instance_type: str


class CompareRequest(BaseModel):
    """Request to compare multiple instances."""
    instances: List[CompareInstanceRequest] = Field(min_length=1, max_length=4)
    hours_per_day: float = Field(ge=0, le=24)
    days_per_week: int = Field(ge=1, le=7)


class CompareResponse(BaseModel):
    """Response for instance comparison."""
    estimates: List[EstimateResponse]


class TimeWindow(BaseModel):
    """Single time window in a schedule."""
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class ScheduleEstimateRequest(BaseModel):
    """Request for schedule-based cost estimation."""
    provider: str = "aws"
    region: str
    instance_type: str
    schedule: Dict[str, List[TimeWindow]]


class Vs24x7(BaseModel):
    """Comparison against 24/7 running."""
    monthly_24x7_cost: float
    monthly_savings: float
    savings_percent: float


class ScheduleEstimateResponse(BaseModel):
    """Response for schedule-based estimation."""
    instance_type: str
    region: str
    hourly_rate: float
    running_hours_per_week: float
    weekly_cost: float
    monthly_cost: float
    annual_cost: float
    vs_24x7: Vs24x7
    currency: str = "USD"
    error: Optional[str] = None
