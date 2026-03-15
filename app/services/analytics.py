from datetime import datetime, timedelta, timezone
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid

from app.models.execution import Execution


class AnalyticsService:
    """Service for execution analytics and statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_execution_statistics(
        self, organization_id: uuid.UUID, hours: int = 24
    ) -> Dict:
        """
        Get execution statistics for a time period.

        Args:
            organization_id: Organization UUID
            hours: Number of hours to look back (default 24)

        Returns:
            Dictionary with statistics
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get all executions in period
        result = await self.db.execute(
            select(Execution).where(
                and_(
                    Execution.organization_id == organization_id,
                    Execution.executed_at >= cutoff_time
                )
            )
        )
        executions = result.scalars().all()

        if not executions:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "actions": {"START": 0, "STOP": 0},
                "period_hours": hours
            }

        # Calculate statistics
        total = len(executions)
        successful = sum(1 for e in executions if e.success)
        failed = total - successful
        success_rate = (successful / total) if total > 0 else 0.0

        # Count actions
        start_count = sum(1 for e in executions if e.action == "START")
        stop_count = sum(1 for e in executions if e.action == "STOP")

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 4),
            "actions": {
                "START": start_count,
                "STOP": stop_count
            },
            "period_hours": hours
        }

    async def get_execution_summary(self, organization_id: uuid.UUID) -> Dict:
        """
        Get dashboard-style execution summary.

        Returns:
            Summary data for dashboard
        """
        # Get stats for different periods
        last_hour = await self.get_execution_statistics(organization_id, hours=1)
        last_24h = await self.get_execution_statistics(organization_id, hours=24)
        last_7d = await self.get_execution_statistics(organization_id, hours=168)

        # Get most recent executions
        result = await self.db.execute(
            select(Execution).where(
                Execution.organization_id == organization_id
            ).order_by(
                Execution.executed_at.desc()
            ).limit(10)
        )
        recent_executions = result.scalars().all()

        # Get failure count in last 24h
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_failures = [
            e for e in recent_executions
            if not e.success and e.executed_at >= cutoff
        ]

        return {
            "last_hour": last_hour,
            "last_24_hours": last_24h,
            "last_7_days": last_7d,
            "recent_failures_count": len(recent_failures),
            "last_execution_at": (
                recent_executions[0].executed_at
                if recent_executions else None
            )
        }

    async def get_resource_execution_count(
        self,
        resource_id: uuid.UUID
    ) -> int:
        """Get total number of executions for a resource."""
        result = await self.db.execute(
            select(func.count()).select_from(Execution).where(
                Execution.resource_id == resource_id
            )
        )
        return result.scalar() or 0

    async def get_resource_execution_timeline(
        self,
        resource_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Execution]:
        """
        Get execution timeline for a specific resource.

        Args:
            resource_id: Resource UUID
            limit: Maximum number of executions to return
            offset: Number of executions to skip

        Returns:
            List of executions ordered by time (newest first)
        """
        result = await self.db.execute(
            select(Execution).where(
                Execution.resource_id == resource_id
            ).order_by(
                Execution.executed_at.desc()
            ).offset(offset).limit(limit)
        )
        return result.scalars().all()
