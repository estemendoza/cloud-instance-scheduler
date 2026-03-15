"""
Manual pricing data update script.

Usage:
    poetry run python -m app.scripts.update_pricing [--provider aws]
    poetry run python -m app.scripts.update_pricing --provider azure --regions eastus,westeurope
    poetry run python -m app.scripts.update_pricing --provider gcp --regions us-east1

If no regions are specified, automatically collects regions from cloud accounts
for the selected provider.
"""

import argparse
import asyncio
import logging
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.models.cloud_account import CloudAccount
from app.models.resource import Resource
from app.services.pricing_fetcher import PricingFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def collect_regions(session, provider_type: str) -> set[str]:
    """Collect regions from provider accounts and discovered resources."""
    regions: set[str] = set()

    # Get all active provider cloud accounts
    result = await session.execute(
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

    # For accounts with null selected_regions, get regions from resources
    if accounts_needing_discovery:
        result = await session.execute(
            select(func.distinct(Resource.region))
            .where(Resource.cloud_account_id.in_(accounts_needing_discovery))
        )
        discovered_regions = result.scalars().all()
        regions.update(r for r in discovered_regions if r)

    return regions


async def main(
    provider_type: str = "aws",
    regions: list[str] | None = None,
):
    provider_type = provider_type.lower()
    logger.info(f"Starting pricing data update for provider={provider_type}...")

    async with AsyncSessionLocal() as session:
        if regions:
            target_regions = regions
            logger.info(f"Using specified regions: {target_regions}")
        else:
            # Auto-discover from cloud accounts
            target_regions = sorted(await collect_regions(session, provider_type))
            if not target_regions:
                logger.warning(
                    f"No {provider_type} regions found in cloud accounts. "
                    "Nothing to update."
                )
                return
            logger.info(
                f"Auto-discovered {len(target_regions)} regions: {target_regions}")

        fetcher = PricingFetcher(session)
        count = await fetcher.update_pricing_db(
            target_regions,
            provider_type=provider_type,
        )
        logger.info(
            f"Successfully updated {count} pricing records for {provider_type}."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update cloud pricing data")
    parser.add_argument(
        "--provider",
        type=str,
        default="aws",
        choices=["aws", "azure", "gcp"],
        help="Cloud provider to update pricing for.",
    )
    parser.add_argument(
        "--regions",
        type=str,
        help="Comma-separated list of regions "
             "(e.g., us-east-1,us-west-2 or eastus,westeurope). "
             "If not specified, auto-discovers from cloud accounts."
    )
    args = parser.parse_args()

    regions = args.regions.split(",") if args.regions else None

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(provider_type=args.provider, regions=regions))
