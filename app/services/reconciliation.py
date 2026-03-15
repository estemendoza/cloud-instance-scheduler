import asyncio
import logging
from datetime import datetime, timezone
from typing import ClassVar, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.resource import Resource
from app.models.cloud_account import CloudAccount
from app.models.execution import Execution
from app.services.policy_engine import PolicyEngine
from app.services.encryption import decrypt_credentials
from app.providers import get_provider, build_credentials
from app.providers.models import InstanceState
from app.models.resource_state_event import ResourceStateEvent

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Service for reconciling desired vs actual resource states."""

    # Class-level lock dictionary shared across all instances
    _org_locks: ClassVar[dict[str, asyncio.Lock]] = {}
    _locks_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, db: AsyncSession):
        self.db = db
        self.policy_engine = PolicyEngine(db)

    @classmethod
    async def get_org_lock(cls, org_id: str) -> asyncio.Lock:
        """Get or create a lock for the given organization."""
        async with cls._locks_lock:
            if org_id not in cls._org_locks:
                cls._org_locks[org_id] = asyncio.Lock()
            return cls._org_locks[org_id]

    async def reconcile_organization(
        self, organization_id: uuid.UUID
    ) -> Dict[str, int]:
        """
        Reconcile all resources for an organization with lock protection.

        Returns:
            Dictionary with counts: {processed, actions_taken, errors}
        """
        lock = await self.get_org_lock(str(organization_id))
        async with lock:
            return await self._do_reconcile_organization(organization_id)

    async def _do_reconcile_organization(
        self, organization_id: uuid.UUID,
    ) -> Dict[str, int]:
        """Reconcile all resources for an org (within lock)."""
        processed = 0
        actions_taken = 0
        errors = 0

        # Get all resources for the organization
        result = await self.db.execute(
            select(Resource).where(Resource.organization_id == organization_id)
        )
        resources = result.scalars().all()

        for resource in resources:
            try:
                action_taken = await self.reconcile_resource(resource)
                processed += 1
                if action_taken:
                    actions_taken += 1
            except Exception as e:
                logger.error(f"Error reconciling resource {resource.id}: {e}")
                errors += 1

        return {
            "processed": processed,
            "actions_taken": actions_taken,
            "errors": errors
        }

    async def trigger_for_policy(self, policy_id: str) -> Dict[str, int]:
        """Trigger reconciliation for resources affected by a policy."""
        from app.models.policy import Policy

        result = await self.db.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        policy = result.scalar_one_or_none()

        if not policy:
            logger.warning(
                f"Policy {policy_id} not found"
                " for reconciliation trigger"
            )
            return {
                "error": "Policy not found",
                "processed": 0,
                "actions_taken": 0,
                "errors": 0,
            }

        logger.info(f"Triggering immediate reconciliation for policy {policy_id}")
        return await self.reconcile_organization(policy.organization_id)

    async def reconcile_resource(self, resource: Resource) -> bool:
        """
        Reconcile a single resource.

        Returns:
            True if an action was taken, False otherwise
        """
        current_time = datetime.now(timezone.utc)

        # Determine desired state using PolicyEngine
        desired_state = await self.policy_engine.get_desired_state(
            resource.id, current_time
        )

        # Get actual state from cache
        actual_state = InstanceState(resource.state)

        # No action needed if states match
        if desired_state == actual_state:
            return False

        # States don't match - take action
        action = "START" if desired_state == InstanceState.RUNNING else "STOP"

        # Get cloud account and provider
        result = await self.db.execute(
            select(CloudAccount).where(CloudAccount.id == resource.cloud_account_id)
        )
        cloud_account = result.scalar_one()

        # Get provider instance
        creds_dict = decrypt_credentials(cloud_account.credentials_encrypted)
        provider = get_provider(
            cloud_account.provider_type,
            build_credentials(cloud_account.provider_type, creds_dict))

        # Create pending execution record before the action
        execution = Execution(
            organization_id=resource.organization_id,
            resource_id=resource.id,
            action=action,
            desired_state=desired_state.value,
            actual_state_before=actual_state.value,
            status="pending",
            success=False,
            error_message=None,
            executed_at=current_time,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)

        # Execute action
        success = False
        error_message = None

        try:
            if action == "START":
                success = await asyncio.to_thread(
                    provider.start_instance,
                    resource.provider_resource_id,
                    resource.region,
                )
            else:  # STOP
                success = await asyncio.to_thread(
                    provider.stop_instance,
                    resource.provider_resource_id,
                    resource.region,
                )

            if success:
                # Update resource cache
                resource.state = desired_state.value
                resource.updated_at = current_time

                # Log state transition
                self.db.add(ResourceStateEvent(
                    organization_id=resource.organization_id,
                    resource_id=resource.id,
                    previous_state=actual_state.value,
                    new_state=desired_state.value,
                    source="reconciliation",
                    changed_at=current_time,
                ))
        except Exception as e:
            error_message = str(e)
            success = False

        # Update execution with result
        execution.status = "completed" if success else "failed"
        execution.success = success
        execution.error_message = error_message

        await self.db.commit()

        return True
