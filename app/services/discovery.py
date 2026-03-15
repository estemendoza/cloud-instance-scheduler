import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.cloud_account import CloudAccount
from app.models.resource import Resource
from app.services.encryption import decrypt_credentials
from app.providers import get_provider, build_credentials
from app.providers.models import InstanceInfo
from app.models.resource_state_event import ResourceStateEvent

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Service for discovering and caching cloud resources."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_provider_credentials(self, cloud_account: CloudAccount):
        """Convert stored credentials to provider-specific credential objects."""
        creds_dict = decrypt_credentials(cloud_account.credentials_encrypted)
        return build_credentials(cloud_account.provider_type, creds_dict)

    async def sync_resources(self, cloud_account_id: uuid.UUID) -> Dict[str, int]:
        """
        Sync resources for a specific cloud account.

        Returns:
            Dictionary with counts: {created, updated, total}
        """
        # Get cloud account
        result = await self.db.execute(
            select(CloudAccount).where(CloudAccount.id == cloud_account_id)
        )
        cloud_account = result.scalar_one_or_none()

        if not cloud_account or not cloud_account.is_active:
            return {"created": 0, "updated": 0, "total": 0}

        # Get provider instance
        credentials = self._get_provider_credentials(cloud_account)
        provider = get_provider(cloud_account.provider_type, credentials)

        # Discover instances from provider (filter by selected regions if specified)
        discovered_instances: List[InstanceInfo] = await asyncio.to_thread(
            provider.list_instances,
            regions=cloud_account.selected_regions
        )

        created_count = 0
        updated_count = 0

        for instance in discovered_instances:
            # Check if resource already exists
            result = await self.db.execute(
                select(Resource).where(
                    Resource.cloud_account_id == cloud_account_id,
                    Resource.provider_resource_id == instance.id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing resource
                old_state = existing.state
                existing.name = instance.name
                existing.state = instance.state.value
                existing.tags = instance.tags
                existing.instance_type = instance.instance_type
                existing.region = instance.region
                existing.last_seen_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)

                if old_state != instance.state.value:
                    self.db.add(ResourceStateEvent(
                        organization_id=cloud_account.organization_id,
                        resource_id=existing.id,
                        previous_state=old_state,
                        new_state=instance.state.value,
                        source="discovery",
                        changed_at=datetime.now(timezone.utc),
                    ))

                updated_count += 1
            else:
                # Create new resource
                new_resource = Resource(
                    organization_id=cloud_account.organization_id,
                    cloud_account_id=cloud_account_id,
                    provider_resource_id=instance.id,
                    name=instance.name,
                    region=instance.region,
                    resource_type="instance",
                    state=instance.state.value,
                    tags=instance.tags,
                    instance_type=instance.instance_type,
                    last_seen_at=datetime.now(timezone.utc)
                )
                self.db.add(new_resource)
                created_count += 1

        # Update cloud account sync timestamp
        cloud_account.last_sync_at = datetime.now(timezone.utc)

        await self.db.commit()

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(discovered_instances)
        }

    async def sync_all_accounts(self, organization_id: uuid.UUID) -> Dict[str, int]:
        """
        Sync all active cloud accounts for an organization.

        Returns:
            Dictionary with aggregate counts
        """
        result = await self.db.execute(
            select(CloudAccount).where(
                CloudAccount.organization_id == organization_id,
                CloudAccount.is_active.is_(True)
            )
        )
        accounts = result.scalars().all()

        total_created = 0
        total_updated = 0
        total_discovered = 0

        for account in accounts:
            try:
                counts = await self.sync_resources(account.id)
                total_created += counts["created"]
                total_updated += counts["updated"]
                total_discovered += counts["total"]
            except Exception as e:
                logger.error("Error syncing account %s: %s", account.id, e)
                continue

        return {
            "created": total_created,
            "updated": total_updated,
            "total": total_discovered,
            "accounts_synced": len(accounts)
        }
