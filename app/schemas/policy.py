from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Dict, List
from datetime import datetime
import uuid
import pytz

from app.services.schedule import ScheduleEvaluator


class PolicyBase(BaseModel):
    name: str
    description: Optional[str] = None
    timezone: str
    schedule_type: str = "weekly"
    schedule: Dict
    resource_selector: Dict
    is_enabled: bool = True

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is a valid IANA timezone."""
        try:
            pytz.timezone(v)
        except pytz.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @field_validator('schedule_type')
    @classmethod
    def validate_schedule_type(cls, v: str) -> str:
        """Validate schedule_type is 'weekly' or 'cron'."""
        if v not in ScheduleEvaluator.VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"schedule_type must be one of: "
                f"{', '.join(ScheduleEvaluator.VALID_SCHEDULE_TYPES)}")
        return v

    @model_validator(mode='after')
    def validate_schedule_matches_type(self):
        """Validate schedule format matches schedule_type."""
        errors = ScheduleEvaluator.validate_schedule(
            self.schedule, self.schedule_type)
        if errors:
            raise ValueError(f"Invalid schedule: {', '.join(errors)}")
        return self

    @field_validator('resource_selector')
    @classmethod
    def validate_resource_selector(cls, v: Dict) -> Dict:
        """Validate resource selector has either tags or resource_ids."""
        if "tags" not in v and "resource_ids" not in v:
            raise ValueError("resource_selector must have 'tags' or 'resource_ids'")
        if "tags" in v and "resource_ids" in v:
            raise ValueError(
                "resource_selector cannot have both 'tags' and 'resource_ids'")
        return v


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    timezone: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule: Optional[Dict] = None
    resource_selector: Optional[Dict] = None
    is_enabled: Optional[bool] = None

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                pytz.timezone(v)
            except pytz.UnknownTimeZoneError:
                raise ValueError(f"Invalid timezone: {v}")
        return v

    @field_validator('schedule_type')
    @classmethod
    def validate_schedule_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ScheduleEvaluator.VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"schedule_type must be one of: "
                f"{', '.join(ScheduleEvaluator.VALID_SCHEDULE_TYPES)}")
        return v

    @model_validator(mode='after')
    def validate_schedule_matches_type(self):
        """Validate schedule format if both schedule and schedule_type are provided."""
        if self.schedule is not None and self.schedule_type is not None:
            errors = ScheduleEvaluator.validate_schedule(
                self.schedule, self.schedule_type)
            if errors:
                raise ValueError(f"Invalid schedule: {', '.join(errors)}")
        elif self.schedule is not None:
            # schedule provided without schedule_type — validate as weekly (default)
            errors = ScheduleEvaluator.validate_schedule(self.schedule, "weekly")
            if errors:
                raise ValueError(f"Invalid schedule: {', '.join(errors)}")
        return self

    @field_validator('resource_selector')
    @classmethod
    def validate_resource_selector(cls, v: Optional[Dict]) -> Optional[Dict]:
        if v is not None:
            if "tags" not in v and "resource_ids" not in v:
                raise ValueError(
                    "resource_selector must have 'tags' or 'resource_ids'")
            if "tags" in v and "resource_ids" in v:
                raise ValueError(
                    "resource_selector cannot have both 'tags' and 'resource_ids'")
        return v


class Policy(PolicyBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PolicyPreview(BaseModel):
    """Preview of resources affected by a policy."""
    policy_id: uuid.UUID
    affected_resource_count: int
    sample_resources: List[uuid.UUID]  # First 10 resources
