from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from app.models.policy import Policy
from app.models.override import Override
from app.models.resource import Resource
from app.services.schedule import ScheduleEvaluator
from app.providers.models import InstanceState


class PolicyEngine:
    """Evaluates policies and overrides to determine desired resource state."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.schedule_evaluator = ScheduleEvaluator()

    async def get_desired_state(
        self,
        resource_id: uuid.UUID,
        current_time: Optional[datetime] = None
    ) -> InstanceState:
        """
        Determine the desired state for a resource.

        Priority:
        1. Active override (if exists and not expired) -> override.desired_state
        2. Enabled policies -> evaluate schedule
        3. Default -> STOPPED

        Args:
            resource_id: UUID of the resource
            current_time: Optional datetime (defaults to now UTC)

        Returns:
            InstanceState (RUNNING or STOPPED)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Get resource
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        resource = result.scalar_one_or_none()

        if not resource:
            return InstanceState.STOPPED

        # Check for active overrides (highest priority)
        override_result = await self.db.execute(
            select(Override).where(
                and_(
                    Override.resource_id == resource_id,
                    Override.expires_at > current_time
                )
            ).order_by(Override.created_at.desc())
        )
        active_override = override_result.scalar_one_or_none()

        if active_override:
            # Override exists and is not expired
            return InstanceState(active_override.desired_state)

        # No active override, evaluate policies
        # Get all enabled policies for this organization
        policies_result = await self.db.execute(
            select(Policy).where(
                and_(
                    Policy.organization_id == resource.organization_id,
                    Policy.is_enabled.is_(True)
                )
            )
        )
        policies = policies_result.scalars().all()

        # Check if any policy applies to this resource and is in running time
        for policy in policies:
            if self._policy_applies_to_resource(policy, resource):
                # Policy applies, check schedule
                if self.schedule_evaluator.is_running_time(
                    policy.schedule,
                    policy.timezone,
                    current_time,
                    schedule_type=policy.schedule_type,
                ):
                    return InstanceState.RUNNING

        # No policy indicates running, default to STOPPED
        return InstanceState.STOPPED

    def _policy_applies_to_resource(self, policy: Policy, resource: Resource) -> bool:
        """Check if a policy applies to a specific resource."""
        selector = policy.resource_selector

        # Check if policy selects by resource IDs
        if "resource_ids" in selector:
            resource_ids = selector["resource_ids"]
            return str(resource.id) in resource_ids

        # Check if policy selects by tags
        if "tags" in selector:
            required_tags = selector["tags"]
            resource_tags = resource.tags or {}

            # All required tags must match
            for key, value in required_tags.items():
                if resource_tags.get(key) != value:
                    return False

            return True

        # Invalid selector
        return False
