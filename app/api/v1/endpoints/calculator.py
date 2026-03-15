from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas.calculator import (
    EstimateRequest,
    EstimateResponse,
    CompareRequest,
    CompareResponse,
    ScheduleEstimateRequest,
    ScheduleEstimateResponse,
    InstanceTypeInfo,
)
from app.services.cost_calculator import CostCalculator

router = APIRouter()


@router.get("/regions", response_model=List[str])
async def get_regions(
    provider: str = Query(default="aws"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get available regions with pricing data."""
    calculator = CostCalculator(db)
    return await calculator.get_available_regions(provider)


@router.get("/instance-types", response_model=List[InstanceTypeInfo])
async def get_instance_types(
    provider: str = Query(default="aws"),
    region: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get available instance types with pricing."""
    calculator = CostCalculator(db)
    results = await calculator.get_instance_types(provider, region)
    return [InstanceTypeInfo(**r) for r in results]


@router.post("/estimate", response_model=EstimateResponse)
async def estimate_cost(
    request: EstimateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Estimate cost for a single instance."""
    calculator = CostCalculator(db)
    result = await calculator.estimate_cost(
        provider=request.provider,
        region=request.region,
        instance_type=request.instance_type,
        hours_per_day=request.hours_per_day,
        days_per_week=request.days_per_week,
    )
    return EstimateResponse(**result)


@router.post("/compare", response_model=CompareResponse)
async def compare_instances(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Compare costs for multiple instances (up to 4)."""
    calculator = CostCalculator(db)
    estimates = []

    for instance in request.instances:
        result = await calculator.estimate_cost(
            provider=instance.provider,
            region=instance.region,
            instance_type=instance.instance_type,
            hours_per_day=request.hours_per_day,
            days_per_week=request.days_per_week,
        )
        estimates.append(EstimateResponse(**result))

    return CompareResponse(estimates=estimates)


@router.post("/schedule-estimate", response_model=ScheduleEstimateResponse)
async def estimate_schedule_cost(
    request: ScheduleEstimateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Estimate cost using a weekly schedule."""
    calculator = CostCalculator(db)

    # Convert schedule to the format expected by the service
    schedule = {
        day: [{"start": w.start, "end": w.end} for w in windows]
        for day, windows in request.schedule.items()
    }

    result = await calculator.estimate_schedule_cost(
        provider=request.provider,
        region=request.region,
        instance_type=request.instance_type,
        schedule=schedule,
    )
    return ScheduleEstimateResponse(**result)
