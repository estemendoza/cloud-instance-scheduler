from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.services.pricing_fetcher import PricingFetcher


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestFetchAzurePricing:
    def test_filters_linux_hourly_and_deduplicates_min_rate(self, mock_db):
        fetcher = PricingFetcher(mock_db)

        page1 = {
            "Items": [
                # Valid Linux hourly VM entry.
                {
                    "serviceName": "Virtual Machines",
                    "armRegionName": "eastus",
                    "armSkuName": "Standard_D2s_v5",
                    "retailPrice": 0.12,
                    "unitOfMeasure": "1 Hour",
                    "productName": "Virtual Machines Dsv5 Series",
                },
                # Duplicate SKU with higher price -> should be ignored.
                {
                    "serviceName": "Virtual Machines",
                    "armRegionName": "eastus",
                    "armSkuName": "Standard_D2s_v5",
                    "retailPrice": 0.15,
                    "unitOfMeasure": "1 Hour",
                    "productName": "Virtual Machines Dsv5 Series",
                },
                # Windows entry -> should be filtered out.
                {
                    "serviceName": "Virtual Machines",
                    "armRegionName": "eastus",
                    "armSkuName": "Standard_D2s_v5",
                    "retailPrice": 0.20,
                    "unitOfMeasure": "1 Hour",
                    "productName": "Virtual Machines Dsv5 Series Windows",
                },
            ],
            "NextPageLink": "https://prices.azure.com/api/retail/prices?$skip=1000",
        }
        page2 = {
            "Items": [
                # Another valid SKU.
                {
                    "serviceName": "Virtual Machines",
                    "armRegionName": "eastus",
                    "armSkuName": "Standard_B2s",
                    "retailPrice": 0.05,
                    "unitOfMeasure": "1 Hour",
                    "productName": "Virtual Machines Bs Series",
                },
                # Wrong unit -> should be filtered out.
                {
                    "serviceName": "Virtual Machines",
                    "armRegionName": "eastus",
                    "armSkuName": "Standard_F2s_v2",
                    "retailPrice": 0.10,
                    "unitOfMeasure": "1 Month",
                    "productName": "Virtual Machines Fsv2 Series",
                },
            ],
            "NextPageLink": None,
        }

        with patch(
            "app.services.pricing_fetcher.requests.get",
            side_effect=[_FakeResponse(page1), _FakeResponse(page2)],
        ):
            data = fetcher.fetch_azure_pricing("eastus")

        assert len(data) == 2
        by_type = {row["instance_type"]: row for row in data}
        assert by_type["Standard_D2s_v5"]["hourly_rate"] == Decimal("0.12")
        assert by_type["Standard_B2s"]["hourly_rate"] == Decimal("0.05")
        assert all(row["provider_type"] == "azure" for row in data)
        assert all(row["region"] == "eastus" for row in data)
        assert all(
            isinstance(row["last_updated"], datetime) and row["last_updated"].tzinfo
            for row in data
        )


class TestUpdatePricingDbDispatcher:
    @pytest.mark.asyncio
    async def test_update_pricing_db_calls_provider_dispatch(self, mock_db):
        fetcher = PricingFetcher(mock_db)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        rows = [
            {
                "provider_type": "azure",
                "region": "eastus",
                "instance_type": "Standard_B2s",
                "hourly_rate": Decimal("0.05"),
                "last_updated": datetime.now(timezone.utc),
            }
        ]

        with patch.object(fetcher, "fetch_pricing", return_value=rows) as mock_fetch:
            updated = await fetcher.update_pricing_db(
                ["eastus"],
                provider_type="azure",
            )

        assert updated == 1
        mock_fetch.assert_called_once_with("azure", "eastus", None)
        assert mock_db.execute.call_count == 1
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_pricing_db_gcp_uses_discovered_instance_types(self, mock_db):
        fetcher = PricingFetcher(mock_db)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        rows = [
            {
                "provider_type": "gcp",
                "region": "us-east1",
                "instance_type": "e2-standard-2",
                "hourly_rate": Decimal("0.10"),
                "last_updated": datetime.now(timezone.utc),
            }
        ]

        with patch.object(
            fetcher,
            "_get_gcp_instance_types_for_region",
            AsyncMock(return_value=["e2-standard-2"]),
        ) as mock_discovered, patch.object(
            fetcher,
            "fetch_pricing",
            return_value=rows,
        ) as mock_fetch:
            updated = await fetcher.update_pricing_db(
                ["us-east1-b"],
                provider_type="gcp",
            )

        assert updated == 1
        mock_discovered.assert_awaited_once_with("us-east1")
        mock_fetch.assert_called_once_with(
            "gcp",
            "us-east1-b",
            ["e2-standard-2"],
        )
        assert mock_db.execute.call_count == 1
        mock_db.commit.assert_awaited_once()


class TestFetchGcpPricing:
    def test_computes_machine_price_from_core_and_ram_rates(self, mock_db):
        fetcher = PricingFetcher(mock_db)

        sku_page = {
            "skus": [
                {
                    "description": "E2 Instance Core running in us-east1",
                    "serviceRegions": ["us-east1"],
                    "category": {
                        "resourceFamily": "Compute",
                        "resourceGroup": "CPU",
                        "usageType": "OnDemand",
                    },
                    "pricingInfo": [
                        {
                            "pricingExpression": {
                                "tieredRates": [
                                    {"unitPrice": {"units": "0", "nanos": 30000000}}
                                ]
                            }
                        }
                    ],
                },
                {
                    "description": "E2 Instance Ram running in us-east1",
                    "serviceRegions": ["us-east1"],
                    "category": {
                        "resourceFamily": "Compute",
                        "resourceGroup": "RAM",
                        "usageType": "OnDemand",
                    },
                    "pricingInfo": [
                        {
                            "pricingExpression": {
                                "tieredRates": [
                                    {"unitPrice": {"units": "0", "nanos": 4000000}}
                                ]
                            }
                        }
                    ],
                },
            ],
            "nextPageToken": None,
        }

        with patch(
            "app.services.pricing_fetcher.requests.get",
            return_value=_FakeResponse(sku_page),
        ), patch.object(
            fetcher, "_get_gcp_auth_headers", return_value={},
        ):
            rows = fetcher.fetch_gcp_pricing(
                "us-east1-b",
                instance_types=["e2-standard-2", "e2-micro", "unknown-type"],
            )

        # e2-standard-2: (2 * 0.03) + (8 * 0.004) = 0.092
        by_type = {row["instance_type"]: row for row in rows}
        assert by_type["e2-standard-2"]["hourly_rate"] == Decimal("0.092")
        # e2-micro: (2 * 0.03) + (1 * 0.004) = 0.064
        assert by_type["e2-micro"]["hourly_rate"] == Decimal("0.064")
        assert "unknown-type" not in by_type
        assert all(row["provider_type"] == "gcp" for row in rows)
        assert all(row["region"] == "us-east1" for row in rows)
