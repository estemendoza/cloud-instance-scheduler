"""Tests for scheduler pricing update functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.services.conftest import make_result


class TestCollectAwsRegions:
    """Tests for _collect_aws_regions helper."""

    @pytest.fixture
    def scheduler_service(self):
        from app.services.scheduler import SchedulerService
        return SchedulerService()

    @pytest.mark.asyncio
    async def test_explicit_regions_from_accounts(self, scheduler_service):
        """Should collect explicit selected_regions from AWS accounts."""
        mock_db = AsyncMock()

        # Mock AWS account with explicit regions
        mock_account = MagicMock()
        mock_account.id = uuid4()
        mock_account.provider_type = "aws"
        mock_account.is_active = True
        mock_account.selected_regions = ["us-east-1", "us-west-2"]

        mock_db.execute.return_value = make_result(scalars=[mock_account])

        regions = await scheduler_service._collect_aws_regions(mock_db)

        assert regions == {"us-east-1", "us-west-2"}

    @pytest.mark.asyncio
    async def test_discovered_regions_from_resources(self, scheduler_service):
        """Should discover regions from resources when selected_regions is null."""
        mock_db = AsyncMock()

        # Mock AWS account with null selected_regions
        mock_account = MagicMock()
        mock_account.id = uuid4()
        mock_account.provider_type = "aws"
        mock_account.is_active = True
        mock_account.selected_regions = None

        # First call returns accounts, second call returns discovered regions
        mock_db.execute.side_effect = [
            make_result(scalars=[mock_account]),
            make_result(scalars=["eu-west-1", "ap-southeast-1"]),
        ]

        regions = await scheduler_service._collect_aws_regions(mock_db)

        assert regions == {"eu-west-1", "ap-southeast-1"}

    @pytest.mark.asyncio
    async def test_combines_explicit_and_discovered(self, scheduler_service):
        """Should combine regions from both sources, deduplicating."""
        mock_db = AsyncMock()

        # Two accounts - one with explicit, one needing discovery
        mock_account_explicit = MagicMock()
        mock_account_explicit.id = uuid4()
        mock_account_explicit.selected_regions = ["us-east-1"]

        mock_account_discover = MagicMock()
        mock_account_discover.id = uuid4()
        mock_account_discover.selected_regions = None

        # First call returns accounts, second call returns discovered regions
        mock_db.execute.side_effect = [
            make_result(scalars=[mock_account_explicit, mock_account_discover]),
            # Note: us-east-1 appears in both - should be deduplicated
            make_result(scalars=["us-east-1", "eu-west-1"]),
        ]

        regions = await scheduler_service._collect_aws_regions(mock_db)

        assert regions == {"us-east-1", "eu-west-1"}

    @pytest.mark.asyncio
    async def test_empty_when_no_aws_accounts(self, scheduler_service):
        """Should return empty set when no AWS accounts exist."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = make_result(scalars=[])

        regions = await scheduler_service._collect_aws_regions(mock_db)

        assert regions == set()

    @pytest.mark.asyncio
    async def test_filters_none_regions(self, scheduler_service):
        """Should filter out None values from discovered regions."""
        mock_db = AsyncMock()

        mock_account = MagicMock()
        mock_account.id = uuid4()
        mock_account.selected_regions = None

        mock_db.execute.side_effect = [
            make_result(scalars=[mock_account]),
            make_result(scalars=["us-east-1", None, "eu-west-1"]),
        ]

        regions = await scheduler_service._collect_aws_regions(mock_db)

        assert regions == {"us-east-1", "eu-west-1"}


class TestRunPricingUpdate:
    """Tests for run_pricing_update job."""

    @pytest.mark.asyncio
    async def test_skips_when_no_regions(self):
        """Should skip gracefully when no regions are found."""
        from app.services.scheduler import SchedulerService

        scheduler_service = SchedulerService()
        scheduler_service.async_session = MagicMock()

        mock_db = AsyncMock()
        scheduler_service.async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_db
        )
        scheduler_service.async_session.return_value.__aexit__ = AsyncMock()

        with patch.object(
            scheduler_service,
            '_collect_aws_regions',
            return_value=set()
        ), patch.object(
            scheduler_service,
            '_collect_azure_regions',
            return_value=set()
        ), patch.object(
            scheduler_service,
            '_collect_gcp_regions',
            return_value=set()
        ):
            # Should not raise
            await scheduler_service.run_pricing_update()

    @pytest.mark.asyncio
    async def test_calls_pricing_fetcher_with_provider_regions(self):
        """Should call PricingFetcher.update_pricing_db per provider/region set."""
        from app.services.scheduler import SchedulerService

        scheduler_service = SchedulerService()
        scheduler_service.async_session = MagicMock()

        mock_db = AsyncMock()
        scheduler_service.async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_db
        )
        scheduler_service.async_session.return_value.__aexit__ = AsyncMock()

        with patch.object(
            scheduler_service,
            '_collect_aws_regions',
            return_value={"us-east-1", "eu-west-1"}
        ), patch.object(
            scheduler_service,
            '_collect_azure_regions',
            return_value={"eastus", "westeurope"}
        ), patch.object(
            scheduler_service,
            '_collect_gcp_regions',
            return_value={"us-east1-b"}
        ), patch.object(
            scheduler_service,
            '_get_gcp_credentials_json',
            new_callable=AsyncMock,
            return_value=None,
        ), patch('app.services.scheduler.PricingFetcher') as MockFetcher:
            mock_fetcher_instance = MagicMock()
            mock_fetcher_instance.update_pricing_db = AsyncMock(
                return_value=1000,
            )
            MockFetcher.return_value = mock_fetcher_instance

            await scheduler_service.run_pricing_update()

            # Verify fetcher was called for all providers
            assert (
                mock_fetcher_instance.update_pricing_db.call_count == 3
            )
            mock_fetcher_instance.update_pricing_db.assert_any_call(
                ["eu-west-1", "us-east-1"],
                provider_type="aws",
            )
            mock_fetcher_instance.update_pricing_db.assert_any_call(
                ["eastus", "westeurope"],
                provider_type="azure",
            )
            mock_fetcher_instance.update_pricing_db.assert_any_call(
                ["us-east1-b"],
                provider_type="gcp",
            )

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self):
        """Should catch exceptions without propagating."""
        from app.services.scheduler import SchedulerService

        scheduler_service = SchedulerService()
        scheduler_service.async_session = MagicMock()

        mock_db = AsyncMock()
        scheduler_service.async_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_db
        )
        scheduler_service.async_session.return_value.__aexit__ = AsyncMock()

        with patch.object(
            scheduler_service,
            '_collect_aws_regions',
            side_effect=Exception("Database error")
        ):
            # Should not raise - errors are logged but not propagated
            await scheduler_service.run_pricing_update()
