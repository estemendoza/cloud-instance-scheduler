from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
import uuid

from app.api.deps import get_db, get_current_active_user, require_role
from app.models.user import User
from app.models.execution import Execution as ExecutionModel
from app.schemas import execution as schemas
from app.services.reconciliation import ReconciliationService
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/", response_model=List[schemas.Execution])
async def list_executions(
    resource_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status"),
    hours: Optional[int] = Query(None, description="Filter to last N hours"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List execution history with optional filters."""
    query = select(ExecutionModel).where(
        ExecutionModel.organization_id == current_user.organization_id
    )

    # Apply filters
    if resource_id:
        query = query.where(ExecutionModel.resource_id == resource_id)
    if action:
        query = query.where(ExecutionModel.action == action)
    if success is not None:
        query = query.where(ExecutionModel.success == success)
    if status:
        query = query.where(ExecutionModel.status == status)
    if hours:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.where(ExecutionModel.executed_at >= cutoff_time)

    query = query.order_by(ExecutionModel.executed_at.desc()
                           ).offset(offset).limit(limit)

    result = await db.execute(query)
    executions = result.scalars().all()

    return executions


@router.get("/count")
async def get_execution_count(
    resource_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status"),
    hours: Optional[int] = Query(None, description="Filter to last N hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get total execution count with optional filters."""
    query = select(func.count()).select_from(ExecutionModel).where(
        ExecutionModel.organization_id == current_user.organization_id
    )

    if resource_id:
        query = query.where(ExecutionModel.resource_id == resource_id)
    if action:
        query = query.where(ExecutionModel.action == action)
    if success is not None:
        query = query.where(ExecutionModel.success == success)
    if status:
        query = query.where(ExecutionModel.status == status)
    if hours:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.where(ExecutionModel.executed_at >= cutoff_time)

    result = await db.execute(query)
    return {"total": result.scalar() or 0}


@router.get("/statistics", response_model=schemas.ExecutionStatistics)
async def get_execution_statistics(
    hours: int = Query(24, description="Time period in hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get execution statistics for a time period."""
    analytics_service = AnalyticsService(db)
    stats = await analytics_service.get_execution_statistics(
        current_user.organization_id,
        hours=hours
    )
    return schemas.ExecutionStatistics(**stats)


@router.get("/summary", response_model=schemas.ExecutionSummary)
async def get_execution_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard-style execution summary."""
    analytics_service = AnalyticsService(db)
    summary = await analytics_service.get_execution_summary(
        current_user.organization_id
    )
    return schemas.ExecutionSummary(**summary)


@router.get("/resources/{resource_id}/timeline/count")
async def get_resource_timeline_count(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get total execution count for a resource."""
    analytics_service = AnalyticsService(db)
    total = await analytics_service.get_resource_execution_count(resource_id)
    return {"total": total}


@router.get("/resources/{resource_id}/timeline", response_model=List[schemas.Execution])
async def get_resource_timeline(
    resource_id: uuid.UUID,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get execution timeline for a specific resource."""
    analytics_service = AnalyticsService(db)
    timeline = await analytics_service.get_resource_execution_timeline(
        resource_id,
        limit=limit,
        offset=offset
    )
    return timeline


@router.post("/reconcile", response_model=schemas.ReconciliationResult)
async def trigger_manual_reconciliation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "operator"))
):
    """Manually trigger reconciliation for the current organization."""
    reconciliation_service = ReconciliationService(db)
    result = await reconciliation_service.reconcile_organization(
        current_user.organization_id
    )

    return schemas.ReconciliationResult(**result)
