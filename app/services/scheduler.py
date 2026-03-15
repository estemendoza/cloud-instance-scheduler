import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker,
)
from sqlalchemy import select, func

from app.core.config import settings
from app.models.user import Organization
from app.models.cloud_account import CloudAccount
from app.models.resource import Resource
from app.models.pricing_job import PricingJobRun
from app.services.reconciliation import ReconciliationService
from app.services.pricing_fetcher import PricingFetcher
from app.services.encryption import decrypt_credentials

logger = logging.getLogger(__name__)


class SchedulerService:
    """Background scheduler for automated reconciliation."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.engine = None
        self.async_session = None

    def start(self):
        """Start the scheduler."""
        self.engine = create_async_engine(
            settings.SQLALCHEMY_DATABASE_URI,
            echo=False,
            pool_pre_ping=True
        )

        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False
        )

        # Schedule reconciliation every 5 minutes
        self.scheduler.add_job(
            self.run_reconciliation_for_all_orgs,
            trigger=IntervalTrigger(minutes=5),
            id="reconciliation_job",
            name="Reconcile all organizations",
            replace_existing=True
        )

        # Schedule daily pricing update
        self.scheduler.add_job(
            self.run_pricing_update,
            trigger=CronTrigger(
                hour=settings.PRICING_UPDATE_HOUR_UTC,
                minute=settings.PRICING_UPDATE_MINUTE_UTC,
                timezone='UTC'
            ),
            id="pricing_update_job",
            name="Update cloud pricing data",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(
            "Scheduler started - reconciliation every 5 min, "
            "pricing daily at "
            f"{settings.PRICING_UPDATE_HOUR_UTC:02d}:"
            f"{settings.PRICING_UPDATE_MINUTE_UTC:02d} UTC"
        )

    async def run_reconciliation_for_all_orgs(self):
        """Run reconciliation for all organizations."""
        logger.info("Starting reconciliation run...")

        async with self.async_session() as db:
            try:
                result = await db.execute(select(Organization))
                orgs = result.scalars().all()

                total_processed = 0
                total_actions = 0
                total_errors = 0

                for org in orgs:
                    try:
                        svc = ReconciliationService(db)
                        stats = (
                            await svc.reconcile_organization(
                                org.id
                            )
                        )

                        total_processed += stats["processed"]
                        total_actions += stats["actions_taken"]
                        total_errors += stats["errors"]

                        logger.info(
                            "Org %s: %d processed,"
                            " %d actions, %d errors",
                            org.name,
                            stats["processed"],
                            stats["actions_taken"],
                            stats["errors"],
                        )
                    except Exception as e:
                        logger.error(
                            "Error reconciling org %s: %s",
                            org.name, e,
                        )
                        continue

                logger.info(
                    "Reconciliation complete:"
                    " %d resources, %d actions, %d errors",
                    total_processed, total_actions, total_errors,
                )
            except Exception as e:
                logger.error("Error in reconciliation run: %s", e)

    async def _collect_regions_for_provider(
        self,
        db: AsyncSession,
        provider_type: str,
    ) -> set[str]:
        """
        Collect all regions that need pricing updates for a
        provider.

        Sources:
        1. Explicit selected_regions from CloudAccount records
        2. Distinct regions from Resources belonging to accounts
           with null selected_regions
        """
        regions: set[str] = set()

        result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.provider_type == provider_type,
                CloudAccount.is_active.is_(True)
            )
        )
        accounts = result.scalars().all()

        accounts_needing_discovery = []

        for account in accounts:
            if account.selected_regions:
                regions.update(account.selected_regions)
            else:
                accounts_needing_discovery.append(account.id)

        if accounts_needing_discovery:
            result = await db.execute(
                select(func.distinct(Resource.region))
                .where(
                    Resource.cloud_account_id.in_(
                        accounts_needing_discovery
                    )
                )
            )
            discovered_regions = result.scalars().all()
            regions.update(r for r in discovered_regions if r)

        logger.info(
            f"Collected {len(regions)} {provider_type} regions "
            f"from {len(accounts)} accounts "
            f"({len(accounts_needing_discovery)} using "
            f"discovered regions)"
        )

        return regions

    async def _collect_aws_regions(
        self, db: AsyncSession,
    ) -> set[str]:
        """Backwards-compatible AWS wrapper."""
        return await self._collect_regions_for_provider(
            db, "aws",
        )

    async def _collect_azure_regions(
        self, db: AsyncSession,
    ) -> set[str]:
        """Collect Azure ARM regions for pricing updates."""
        return await self._collect_regions_for_provider(
            db, "azure",
        )

    async def _collect_gcp_regions(
        self, db: AsyncSession,
    ) -> set[str]:
        """Collect GCP zones/regions for pricing updates."""
        return await self._collect_regions_for_provider(
            db, "gcp",
        )

    async def _get_gcp_credentials_json(
        self,
        db: AsyncSession,
        cloud_account_id: str = None,
    ) -> str | None:
        """Get GCP service account JSON for pricing.

        If cloud_account_id is specified, use that account.
        Otherwise, pick the first active GCP cloud account.
        """
        if cloud_account_id:
            result = await db.execute(
                select(CloudAccount).where(
                    CloudAccount.id == cloud_account_id,
                    CloudAccount.provider_type == "gcp",
                    CloudAccount.is_active.is_(True),
                )
            )
        else:
            result = await db.execute(
                select(CloudAccount).where(
                    CloudAccount.provider_type == "gcp",
                    CloudAccount.is_active.is_(True),
                ).limit(1)
            )

        account = result.scalar_one_or_none()
        if not account:
            return None

        try:
            creds = decrypt_credentials(
                account.credentials_encrypted
            )
            return creds.get("service_account_json")
        except Exception as e:
            logger.error(
                f"Failed to decrypt GCP credentials for"
                f" account {account.id}: {e}"
            )
            return None

    async def run_pricing_update_for_provider(
        self,
        db: AsyncSession,
        provider_type: str,
        regions: list[str],
        trigger: str = "scheduled",
        gcp_pricing_account_id: str = None,
    ) -> PricingJobRun:
        """Run pricing update for one provider with job tracking.

        Creates a PricingJobRun record, runs the update, and
        persists the result.
        """
        job = PricingJobRun(
            provider_type=provider_type,
            status="running",
            trigger=trigger,
            regions_requested=len(regions),
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()

        try:
            gcp_json = None
            if provider_type == "gcp":
                gcp_json = (
                    await self._get_gcp_credentials_json(
                        db, gcp_pricing_account_id,
                    )
                )
            fetcher = PricingFetcher(
                db, gcp_credentials_json=gcp_json,
            )
            updated = await fetcher.update_pricing_db(
                regions, provider_type=provider_type,
            )
            job.status = "completed"
            job.records_updated = updated
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            logger.error(
                f"Pricing update failed for {provider_type}:"
                f" {e}",
                exc_info=True,
            )
        finally:
            job.completed_at = datetime.now(timezone.utc)
            job.duration_seconds = (
                job.completed_at - job.started_at
            ).total_seconds()
            await db.commit()

        return job

    async def run_pricing_update(self):
        """Run daily pricing update for all providers in use."""
        start_time = datetime.now(timezone.utc)
        logger.info(
            f"[{start_time}] Starting daily pricing update..."
        )

        async with self.async_session() as db:
            try:
                total_updated = 0

                provider_regions = {
                    "aws": await self._collect_aws_regions(db),
                    "azure": await self._collect_azure_regions(
                        db
                    ),
                    "gcp": await self._collect_gcp_regions(db),
                }

                for ptype, regions in provider_regions.items():
                    if not regions:
                        logger.info(
                            f"No {ptype} regions to update"
                            " pricing for - skipping"
                        )
                        continue

                    region_list = sorted(list(regions))
                    logger.info(
                        f"Updating {ptype} pricing for "
                        f"{len(region_list)} regions:"
                        f" {region_list}"
                    )
                    job = (
                        await
                        self.run_pricing_update_for_provider(
                            db, ptype, region_list,
                            trigger="scheduled",
                        )
                    )
                    if job.records_updated:
                        total_updated += job.records_updated

                duration = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()
                logger.info(
                    f"Pricing update complete:"
                    f" {total_updated} records"
                    f" in {duration:.1f}s"
                )

            except Exception as e:
                logger.error(
                    f"Error in pricing update: {e}",
                    exc_info=True,
                )

    async def shutdown(self):
        """Shutdown the scheduler gracefully."""
        self.scheduler.shutdown(wait=True)
        if self.engine:
            await self.engine.dispose()
        logger.info("Scheduler stopped")


# Global scheduler instance
scheduler_service = SchedulerService()
