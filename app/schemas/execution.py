from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import uuid


class ExecutionBase(BaseModel):
    resource_id: uuid.UUID
    action: str
    desired_state: str
    actual_state_before: str
    status: str = "completed"  # pending, completed, failed
    success: bool
    error_message: Optional[str] = None


class Execution(ExecutionBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    executed_at: datetime

    class Config:
        from_attributes = True


class ReconciliationResult(BaseModel):
    """Result of a manual reconciliation run."""
    processed: int
    actions_taken: int
    errors: int


class ExecutionStatistics(BaseModel):
    """Aggregated execution statistics for a time period."""
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    actions: Dict[str, int]  # {"START": count, "STOP": count}
    period_hours: int


class ExecutionSummary(BaseModel):
    """Dashboard-style execution summary."""
    last_hour: ExecutionStatistics
    last_24_hours: ExecutionStatistics
    last_7_days: ExecutionStatistics
    recent_failures_count: int
    last_execution_at: Optional[datetime] = None
