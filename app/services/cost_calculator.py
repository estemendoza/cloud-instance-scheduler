from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
import uuid

from app.models.resource import Resource
from app.models.cloud_account import CloudAccount
from app.models.policy import Policy
from app.models.pricing import InstancePricing
from app.services.schedule import ScheduleEvaluator


class CostCalculator:
    """Service for calculating cost savings estimates."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.schedule_evaluator = ScheduleEvaluator()

    @staticmethod
    def _normalize_gcp_region(region_or_zone: str) -> str:
        """Convert GCP zone (us-east1-b) to region (us-east1)."""
        parts = region_or_zone.split("-")
        if len(parts) >= 3 and len(parts[-1]) == 1:
            return "-".join(parts[:-1])
        return region_or_zone

    async def get_hourly_rate(
        self,
        provider_type: str,
        region: str,
        instance_type: str
    ) -> Optional[Decimal]:
        """Get hourly rate for an instance type."""
        result = await self.db.execute(
            select(InstancePricing).where(
                InstancePricing.provider_type == provider_type,
                InstancePricing.region == region,
                InstancePricing.instance_type == instance_type
            )
        )
        pricing = result.scalar_one_or_none()
        if pricing:
            return pricing.hourly_rate

        # GCP resources store zones; pricing is region-scoped.
        if provider_type == "gcp":
            normalized_region = self._normalize_gcp_region(region)
            if normalized_region != region:
                result = await self.db.execute(
                    select(InstancePricing).where(
                        InstancePricing.provider_type == provider_type,
                        InstancePricing.region == normalized_region,
                        InstancePricing.instance_type == instance_type
                    )
                )
                pricing = result.scalar_one_or_none()
        return pricing.hourly_rate if pricing else None

    def calculate_stopped_hours_per_week(
        self, schedule: Dict, schedule_type: str = "weekly"
    ) -> float:
        """
        Calculate how many hours per week instance is stopped based on schedule.

        Args:
            schedule: Schedule dict (weekly or cron format)
            schedule_type: "weekly" or "cron"

        Returns:
            Hours per week the instance is stopped
        """
        running_hours = self.calculate_running_hours_per_week(
            schedule, schedule_type=schedule_type)
        return max(0.0, 168.0 - running_hours)

    async def calculate_resource_savings(self, resource_id: uuid.UUID) -> Dict:
        """
        Calculate estimated savings for a specific resource.

        Returns:
            Dict with savings breakdown
        """
        # Get resource
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        resource = result.scalar_one_or_none()

        if not resource or not resource.instance_type:
            return {
                "resource_id": str(resource.id) if resource else "",
                "instance_type": (
                    (resource.instance_type or "")
                    if resource else ""
                ),
                "hourly_rate": 0.0,
                "stopped_hours_per_week": 0.0,
                "monthly_savings": 0.0,
                "annual_savings": 0.0,
                "currency": "USD",
                "note": "No instance type or resource not found"
            }

        # Get cloud account for provider type
        result = await self.db.execute(
            select(CloudAccount).where(CloudAccount.id == resource.cloud_account_id)
        )
        cloud_account = result.scalar_one_or_none()

        if not cloud_account:
            return {
                "resource_id": str(resource.id),
                "instance_type": resource.instance_type or "",
                "hourly_rate": 0.0,
                "stopped_hours_per_week": 0.0,
                "monthly_savings": 0.0,
                "annual_savings": 0.0,
                "currency": "USD",
                "note": "Cloud account not found"
            }

        # Get hourly rate
        hourly_rate = await self.get_hourly_rate(
            cloud_account.provider_type,
            resource.region,
            resource.instance_type
        )

        if not hourly_rate:
            return {
                "resource_id": str(resource.id),
                "instance_type": resource.instance_type,
                "hourly_rate": 0.0,
                "stopped_hours_per_week": 0.0,
                "monthly_savings": 0.0,
                "annual_savings": 0.0,
                "currency": "USD",
                "note": (
                    f"Pricing not available for "
                    f"{resource.instance_type} in {resource.region}"
                )
            }

        # Find applicable policies
        policies_result = await self.db.execute(
            select(Policy).where(
                Policy.organization_id == resource.organization_id,
                Policy.is_enabled.is_(True)
            )
        )
        policies = policies_result.scalars().all()

        # Find policy that applies to this resource
        applicable_policy = None
        for policy in policies:
            selector = policy.resource_selector

            # Check by resource ID
            if (
                "resource_ids" in selector
                and str(resource.id) in selector["resource_ids"]
            ):
                applicable_policy = policy
                break

            # Check by tags
            if "tags" in selector:
                required_tags = selector["tags"]
                resource_tags = resource.tags or {}

                match = all(
                    resource_tags.get(k) == v
                    for k, v in required_tags.items()
                )
                if match:
                    applicable_policy = policy
                    break

        if not applicable_policy:
            return {
                "resource_id": str(resource.id),
                "instance_type": resource.instance_type,
                "hourly_rate": float(hourly_rate),
                "stopped_hours_per_week": 0.0,
                "monthly_savings": 0.0,
                "annual_savings": 0.0,
                "currency": "USD",
                "note": "No active policy applies to this resource"
            }

        # Calculate stopped hours
        schedule_type = getattr(applicable_policy, 'schedule_type', 'weekly')
        stopped_hours_per_week = self.calculate_stopped_hours_per_week(
            applicable_policy.schedule, schedule_type=schedule_type)

        # Calculate savings
        # 4.33 weeks per month average
        monthly_stopped_hours = stopped_hours_per_week * 4.33
        monthly_savings = float(hourly_rate) * monthly_stopped_hours
        annual_savings = monthly_savings * 12

        return {
            "resource_id": str(resource.id),
            "instance_type": resource.instance_type,
            "hourly_rate": float(hourly_rate),
            "stopped_hours_per_week": stopped_hours_per_week,
            "monthly_savings": round(monthly_savings, 2),
            "annual_savings": round(annual_savings, 2),
            "currency": "USD",
            "policy_name": applicable_policy.name
        }

    async def calculate_organization_savings(
        self, organization_id: uuid.UUID
    ) -> Dict:
        """
        Calculate total estimated savings for an organization.

        Returns:
            Aggregated savings for all resources
        """
        # Get all resources
        result = await self.db.execute(
            select(Resource).where(Resource.organization_id == organization_id)
        )
        resources = result.scalars().all()

        total_monthly = 0.0
        total_annual = 0.0
        resource_count = 0

        for resource in resources:
            savings = await self.calculate_resource_savings(resource.id)
            if savings.get("monthly_savings", 0) > 0:
                total_monthly += savings["monthly_savings"]
                total_annual += savings["annual_savings"]
                resource_count += 1

        return {
            "total_monthly_savings": round(total_monthly, 2),
            "total_annual_savings": round(total_annual, 2),
            "currency": "USD",
            "resources_with_savings": resource_count,
            "total_resources": len(resources)
        }

    # ===== Calculator Methods =====

    async def get_available_regions(self, provider: str = "aws") -> List[str]:
        """Get list of regions with pricing data available."""
        result = await self.db.execute(
            select(distinct(InstancePricing.region))
            .where(InstancePricing.provider_type == provider)
            .order_by(InstancePricing.region)
        )
        return [row[0] for row in result.fetchall()]

    async def get_instance_types(
        self,
        provider: str = "aws",
        region: Optional[str] = None
    ) -> List[Dict]:
        """Get available instance types with pricing."""
        query = select(
            InstancePricing.instance_type,
            InstancePricing.hourly_rate,
            InstancePricing.region
        ).where(InstancePricing.provider_type == provider)

        if region:
            query = query.where(InstancePricing.region == region)

        query = query.order_by(InstancePricing.instance_type)

        result = await self.db.execute(query)
        return [
            {
                "instance_type": row.instance_type,
                "hourly_rate": float(row.hourly_rate),
                "region": row.region
            }
            for row in result.fetchall()
        ]

    def calculate_running_hours_per_week(
        self, schedule: Dict, schedule_type: str = "weekly"
    ) -> float:
        """Calculate running hours per week from a schedule."""
        if schedule_type == "cron":
            return ScheduleEvaluator.calculate_cron_running_hours_per_week(
                schedule)

        # Weekly: sum up time windows
        total_running_hours = 0.0
        for day in ScheduleEvaluator.DAYS_OF_WEEK:
            day_windows = schedule.get(day, [])
            for window in day_windows:
                try:
                    start_time = ScheduleEvaluator._parse_time(window["start"])
                    end_time = ScheduleEvaluator._parse_time(window["end"])
                    hours = (
                        (end_time.hour - start_time.hour)
                        + (end_time.minute - start_time.minute) / 60.0
                    )
                    total_running_hours += hours
                except (ValueError, KeyError):
                    continue
        return total_running_hours

    async def estimate_cost(
        self,
        provider: str,
        region: str,
        instance_type: str,
        hours_per_day: float,
        days_per_week: int
    ) -> Dict:
        """
        Estimate costs for an instance with simple hours/days input.

        Args:
            provider: Cloud provider (e.g., "aws")
            region: Region code (e.g., "us-east-1")
            instance_type: Instance type (e.g., "t3.medium")
            hours_per_day: Hours running per day
            days_per_week: Days running per week

        Returns:
            Cost breakdown dict
        """
        hourly_rate = await self.get_hourly_rate(provider, region, instance_type)

        if not hourly_rate:
            return {
                "error": f"Pricing not available for {instance_type} in {region}",
                "hourly_rate": 0.0,
                "daily_cost": 0.0,
                "weekly_cost": 0.0,
                "monthly_cost": 0.0,
                "annual_cost": 0.0,
                "currency": "USD"
            }

        rate = float(hourly_rate)
        daily_cost = rate * hours_per_day
        weekly_cost = daily_cost * days_per_week
        monthly_cost = weekly_cost * 4.33
        annual_cost = monthly_cost * 12

        return {
            "instance_type": instance_type,
            "region": region,
            "hourly_rate": rate,
            "hours_per_day": hours_per_day,
            "days_per_week": days_per_week,
            "daily_cost": round(daily_cost, 2),
            "weekly_cost": round(weekly_cost, 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(annual_cost, 2),
            "currency": "USD"
        }

    async def estimate_schedule_cost(
        self,
        provider: str,
        region: str,
        instance_type: str,
        schedule: Dict
    ) -> Dict:
        """
        Estimate costs using a weekly schedule.

        Args:
            provider: Cloud provider
            region: Region code
            instance_type: Instance type
            schedule: Weekly schedule dict (same format as policies)

        Returns:
            Cost breakdown with comparison to 24/7 running
        """
        hourly_rate = await self.get_hourly_rate(provider, region, instance_type)

        if not hourly_rate:
            return {
                "error": f"Pricing not available for {instance_type} in {region}",
                "hourly_rate": 0.0,
                "running_hours_per_week": 0.0,
                "weekly_cost": 0.0,
                "monthly_cost": 0.0,
                "annual_cost": 0.0,
                "vs_24x7": {"monthly_savings": 0.0, "savings_percent": 0.0},
                "currency": "USD"
            }

        rate = float(hourly_rate)
        running_hours = self.calculate_running_hours_per_week(schedule)

        weekly_cost = rate * running_hours
        monthly_cost = weekly_cost * 4.33
        annual_cost = monthly_cost * 12

        # Calculate 24/7 cost for comparison
        weekly_24x7 = rate * 168
        monthly_24x7 = weekly_24x7 * 4.33

        monthly_savings = monthly_24x7 - monthly_cost
        savings_percent = (
            monthly_savings / monthly_24x7 * 100
        ) if monthly_24x7 > 0 else 0.0

        return {
            "instance_type": instance_type,
            "region": region,
            "hourly_rate": rate,
            "running_hours_per_week": round(running_hours, 1),
            "weekly_cost": round(weekly_cost, 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(annual_cost, 2),
            "vs_24x7": {
                "monthly_24x7_cost": round(monthly_24x7, 2),
                "monthly_savings": round(monthly_savings, 2),
                "savings_percent": round(savings_percent, 1)
            },
            "currency": "USD"
        }
