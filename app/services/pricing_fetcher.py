import asyncio
import logging
import re
import requests
import ijson
import os
import tempfile
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, func

from google.oauth2 import service_account
import google.auth.transport.requests as google_auth_requests

from app.models.pricing import InstancePricing
from app.models.resource import Resource
from app.models.cloud_account import CloudAccount

logger = logging.getLogger(__name__)


class PricingFetcher:
    """Service to fetch and update cloud instance pricing."""

    AWS_PRICING_API_HOST = "https://pricing.us-east-1.amazonaws.com"
    AWS_INDEX_URL = (
        f"{AWS_PRICING_API_HOST}"
        "/offers/v1.0/aws/AmazonEC2/current/region_index.json"
    )
    AZURE_PRICING_API_URL = "https://prices.azure.com/api/retail/prices"
    GCP_PRICING_API_URL = (
        "https://cloudbilling.googleapis.com"
        "/v1/services/6F81-5844-456A/skus"
    )

    # GiB per vCPU for common GCP predefined machine families.
    GCP_MEMORY_PROFILE = {
        "standard": Decimal("4"),
        "highmem": Decimal("8"),
        "highcpu": Decimal("1"),
    }
    # Shared-core E2 machine types.
    GCP_SHARED_TYPES: Dict[str, Tuple[Decimal, Decimal]] = {
        "e2-micro": (Decimal("2"), Decimal("1")),   # vCPU, GiB
        "e2-small": (Decimal("2"), Decimal("2")),
        "e2-medium": (Decimal("2"), Decimal("4")),
    }

    def __init__(
        self,
        db: AsyncSession,
        gcp_credentials_json: Optional[str] = None,
    ):
        self.db = db
        self._gcp_credentials_json = gcp_credentials_json

    def _get_gcp_auth_headers(self) -> Dict[str, str]:
        """Get auth headers from a GCP service account JSON.

        Uses the service account credentials from a configured
        GCP cloud account (passed via gcp_credentials_json).
        """
        if not self._gcp_credentials_json:
            logger.warning(
                "No GCP credentials configured for pricing. "
                "Select a GCP cloud account for pricing in "
                "Settings > Pricing."
            )
            return {}

        try:
            import json
            sa_info = json.loads(self._gcp_credentials_json)
            # Always create fresh credentials to avoid
            # stale JWT / clock-skew issues.
            creds = (
                service_account.Credentials
                .from_service_account_info(
                    sa_info,
                    scopes=[
                        "https://www.googleapis.com/"
                        "auth/cloud-platform"
                    ],
                )
            )
            creds.refresh(
                google_auth_requests.Request()
            )
            return {
                "Authorization":
                f"Bearer {creds.token}"
            }
        except Exception as e:
            logger.error(
                f"Failed to authenticate with GCP service "
                f"account for pricing: {e}"
            )
            return {}

    def _get_region_index(self) -> Dict:
        """Fetch the AWS region index."""
        try:
            response = requests.get(self.AWS_INDEX_URL, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch AWS region index: {e}")
            return {}

    def fetch_aws_pricing(self, region_code: str) -> List[Dict]:
        """
        Fetch AWS pricing for a specific region.
        Returns a list of pricing dicts ready for insertion.
        """
        index = self._get_region_index()
        regions = index.get("regions", {})

        if region_code not in regions:
            logger.error(f"Region {region_code} not found in AWS pricing index")
            return []

        region_url_path = regions[region_code]["currentVersionUrl"]
        full_url = f"{self.AWS_PRICING_API_HOST}{region_url_path}"

        logger.info(f"Fetching pricing data for {region_code} from {full_url}")

        valid_skus: Dict[str, str] = {}  # sku -> instance_type
        pricing_data = []

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            temp_path = tmp_file.name
            try:
                # Download to temp file
                with requests.get(full_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=8192):
                        tmp_file.write(chunk)
                # Close to ensure data is flushed for reading
                tmp_file.close()

                # Pass 1: Scan products to find valid SKUs
                logger.info(f"Parsing products for {region_code}...")
                with open(temp_path, 'rb') as f:
                    # ijson.kvitems yields (key, value) pairs from a dictionary
                    products = ijson.kvitems(f, "products")
                    for sku, product in products:
                        attributes = product.get("attributes", {})

                        if (attributes.get("servicecode") != "AmazonEC2" or
                            attributes.get("tenancy") != "Shared" or
                            attributes.get("operatingSystem") != "Linux" or
                            attributes.get("preInstalledSw") != "NA" or
                                attributes.get("capacitystatus") != "Used"):
                            continue

                        instance_type = attributes.get("instanceType")
                        if instance_type:
                            valid_skus[sku] = instance_type

                logger.info(f"Found {len(valid_skus)} valid SKUs for {region_code}")

                # Pass 2: Scan terms to find prices
                logger.info(f"Parsing terms for {region_code}...")
                with open(temp_path, 'rb') as f:
                    # terms.OnDemand is a dict of sku -> offer_dict
                    terms = ijson.kvitems(f, "terms.OnDemand")
                    for sku, sku_terms in terms:
                        if sku not in valid_skus:
                            continue

                        instance_type = valid_skus[sku]

                        # Iterate through offer terms
                        for offer_code, offer in sku_terms.items():
                            price_dimensions = offer.get("priceDimensions", {})
                            for pd_code, pd in price_dimensions.items():
                                price_per_unit = pd.get("pricePerUnit", {}).get("USD")
                                unit = pd.get("unit")

                                if unit == "Hrs" and price_per_unit:
                                    try:
                                        rate = Decimal(price_per_unit)
                                        if rate > 0:
                                            pricing_data.append(
                                                {"provider_type": "aws",
                                                 "region": region_code,
                                                 "instance_type": instance_type,
                                                 "hourly_rate": rate,
                                                 "last_updated": datetime.now(
                                                     timezone.utc)})
                                    except (ValueError, TypeError):
                                        continue

            except Exception as e:
                logger.error(f"Failed to process pricing data for {region_code}: {e}")
                return []
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        logger.info(f"Found {len(pricing_data)} pricing records for {region_code}")
        return pricing_data

    def fetch_azure_pricing(self, region_code: str) -> List[Dict]:
        """
        Fetch Azure VM on-demand Linux pricing for a specific region.

        Returns a list of pricing dicts ready for insertion.
        """
        logger.info(f"Fetching Azure pricing for {region_code}")

        # Keep scope tight: VM compute pricing in a specific ARM region.
        filter_query = (
            "serviceName eq 'Virtual Machines' "
            f"and armRegionName eq '{region_code}' "
            "and priceType eq 'Consumption'"
        )
        next_url = f"{self.AZURE_PRICING_API_URL}?$filter={filter_query}"

        # Some SKUs appear multiple times (different meter/product entries).
        # Keep the lowest positive hourly Linux price per SKU.
        min_hourly_rate_by_sku: Dict[str, Decimal] = {}

        try:
            while next_url:
                response = requests.get(next_url, timeout=30)
                response.raise_for_status()
                payload = response.json()

                for item in payload.get("Items", []):
                    if item.get("serviceName") != "Virtual Machines":
                        continue

                    if item.get("armRegionName") != region_code:
                        continue

                    unit = item.get("unitOfMeasure", "")
                    if "hour" not in unit.lower():
                        continue

                    # Align with AWS behavior (Linux compute cost baseline).
                    product_name = (item.get("productName") or "").lower()
                    if "windows" in product_name:
                        continue

                    sku = item.get("armSkuName")
                    if not sku:
                        continue

                    price_value = item.get("retailPrice")
                    if price_value is None:
                        continue

                    try:
                        rate = Decimal(str(price_value))
                    except Exception:
                        continue

                    if rate <= 0:
                        continue

                    existing = min_hourly_rate_by_sku.get(sku)
                    if existing is None or rate < existing:
                        min_hourly_rate_by_sku[sku] = rate

                next_url = payload.get("NextPageLink")

        except Exception as e:
            logger.error(f"Failed to fetch Azure pricing for {region_code}: {e}")
            return []

        pricing_data = [
            {
                "provider_type": "azure",
                "region": region_code,
                "instance_type": sku,
                "hourly_rate": rate,
                "last_updated": datetime.now(timezone.utc),
            }
            for sku, rate in min_hourly_rate_by_sku.items()
        ]

        logger.info(
            f"Found {len(pricing_data)} Azure pricing records for {region_code}"
        )
        return pricing_data

    @staticmethod
    def _normalize_gcp_region(region_or_zone: str) -> str:
        """
        Convert a GCP zone (e.g. us-east1-b) to region (us-east1).
        If already a region, return as-is.
        """
        if not region_or_zone:
            return region_or_zone
        parts = region_or_zone.split("-")
        if len(parts) >= 3 and len(parts[-1]) == 1:
            return "-".join(parts[:-1])
        return region_or_zone

    @staticmethod
    def _gcp_unit_price_to_decimal(unit_price: Dict) -> Optional[Decimal]:
        """Convert GCP unitPrice object {units, nanos} to Decimal."""
        if not unit_price:
            return None
        units = Decimal(str(unit_price.get("units", "0")))
        nanos = Decimal(str(unit_price.get("nanos", 0))) / Decimal("1000000000")
        return units + nanos

    @staticmethod
    def _extract_gcp_family_from_description(description: str) -> Optional[str]:
        """Extract machine family from GCP SKU description."""
        desc = description.lower()
        for family in ["n1", "n2", "n2d", "e2", "c2", "c2d", "t2d"]:
            if family in desc:
                return family
        return None

    def _calculate_gcp_machine_hourly_rate(
        self,
        instance_type: str,
        core_rates: Dict[str, Decimal],
        ram_rates: Dict[str, Decimal],
    ) -> Optional[Decimal]:
        """Compute an hourly instance rate from per-family core/ram rates."""
        lower_type = instance_type.lower()

        if lower_type in self.GCP_SHARED_TYPES:
            family = lower_type.split("-", 1)[0]
            core_rate = core_rates.get(family)
            ram_rate = ram_rates.get(family)
            if core_rate is None or ram_rate is None:
                return None
            vcpus, gib = self.GCP_SHARED_TYPES[lower_type]
            return (vcpus * core_rate) + (gib * ram_rate)

        custom_match = re.match(
            r"^(?P<family>[a-z0-9]+)-custom-(?P<vcpus>\d+)-(?P<memory_mb>\d+)$",
            lower_type,
        )
        if custom_match:
            family = custom_match.group("family")
            core_rate = core_rates.get(family)
            ram_rate = ram_rates.get(family)
            if core_rate is None or ram_rate is None:
                return None
            vcpus = Decimal(custom_match.group("vcpus"))
            memory_gib = Decimal(custom_match.group("memory_mb")) / Decimal("1024")
            return (vcpus * core_rate) + (memory_gib * ram_rate)

        predefined_match = re.match(
            r"^(?P<family>[a-z0-9]+)-"
            r"(?P<shape>standard|highmem|highcpu)-"
            r"(?P<size>\d+)$",
            lower_type,
        )
        if not predefined_match:
            return None

        family = predefined_match.group("family")
        shape = predefined_match.group("shape")
        vcpus = Decimal(predefined_match.group("size"))
        core_rate = core_rates.get(family)
        ram_rate = ram_rates.get(family)
        gib_per_vcpu = self.GCP_MEMORY_PROFILE.get(shape)
        if core_rate is None or ram_rate is None or gib_per_vcpu is None:
            return None

        memory_gib = vcpus * gib_per_vcpu
        return (vcpus * core_rate) + (memory_gib * ram_rate)

    async def _get_gcp_instance_types_for_region(self, region_code: str) -> List[str]:
        """Collect discovered GCP instance types for a region."""
        result = await self.db.execute(
            select(func.distinct(Resource.instance_type))
            .select_from(Resource)
            .join(CloudAccount, CloudAccount.id == Resource.cloud_account_id)
            .where(
                CloudAccount.provider_type == "gcp",
                Resource.instance_type.is_not(None),
            )
        )
        all_types = [row for row in result.scalars().all() if row]

        # Narrow to resources in the target region (zone or region value).
        region_prefix = f"{region_code}-"
        resources_result = await self.db.execute(
            select(func.distinct(Resource.instance_type))
            .select_from(Resource)
            .join(CloudAccount, CloudAccount.id == Resource.cloud_account_id)
            .where(
                CloudAccount.provider_type == "gcp",
                Resource.instance_type.is_not(None),
                (
                    (Resource.region == region_code) |
                    (Resource.region.like(f"{region_prefix}%"))
                ),
            )
        )
        scoped_types = [row for row in resources_result.scalars().all() if row]

        # Prefer scoped values; fall back to all if region-scoped resources don't exist.
        return sorted(set(scoped_types or all_types))

    # Families we extract pricing for.
    GCP_KNOWN_FAMILIES = {
        "n1", "n2", "n2d", "e2", "c2", "c2d", "t2d",
    }

    def fetch_gcp_pricing(
        self,
        region_code: str,
        instance_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Fetch GCP pricing by combining per-family core+ram on-demand Linux rates.

        The Billing Catalog exposes CPU and RAM SKUs separately. We compute
        hourly prices for discovered instance types in the target region.
        """
        region = self._normalize_gcp_region(region_code)
        logger.info(
            f"Fetching GCP pricing for {region} "
            f"(input={region_code})"
        )

        next_page_token = None
        core_rates: Dict[str, Decimal] = {}
        ram_rates: Dict[str, Decimal] = {}

        auth_headers = self._get_gcp_auth_headers()
        target_families = set(self.GCP_KNOWN_FAMILIES)
        pages_fetched = 0

        try:
            while True:
                params = {
                    "currencyCode": "USD",
                    "pageSize": 5000,
                }
                if next_page_token:
                    params["pageToken"] = next_page_token

                response = requests.get(
                    self.GCP_PRICING_API_URL,
                    params=params,
                    headers=auth_headers,
                    timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
                pages_fetched += 1

                for sku in payload.get("skus", []):
                    category = sku.get("category", {})
                    if category.get("usageType") != "OnDemand":
                        continue
                    if (
                        category.get("resourceFamily")
                        != "Compute"
                    ):
                        continue
                    if category.get("resourceGroup") not in {
                        "CPU", "RAM",
                    }:
                        continue
                    if region not in (
                        sku.get("serviceRegions") or []
                    ):
                        continue

                    description = sku.get("description", "")
                    if "sole tenancy" in description.lower():
                        continue
                    family = (
                        self
                        ._extract_gcp_family_from_description(
                            description,
                        )
                    )
                    if not family:
                        continue

                    pricing_info = (
                        sku.get("pricingInfo") or []
                    )
                    if not pricing_info:
                        continue
                    expression = pricing_info[0].get(
                        "pricingExpression", {},
                    )
                    tiered_rates = expression.get(
                        "tieredRates", [],
                    )
                    if not tiered_rates:
                        continue
                    price = self._gcp_unit_price_to_decimal(
                        tiered_rates[0].get("unitPrice", {})
                    )
                    if price is None or price <= 0:
                        continue

                    if (
                        category.get("resourceGroup") == "CPU"
                    ):
                        current = core_rates.get(family)
                        if current is None or price < current:
                            core_rates[family] = price
                    else:
                        current = ram_rates.get(family)
                        if current is None or price < current:
                            ram_rates[family] = price

                # Stop early if we have both core and RAM
                # rates for all known families.
                if (
                    target_families <= core_rates.keys()
                    and target_families <= ram_rates.keys()
                ):
                    logger.info(
                        f"Collected all {len(target_families)}"
                        f" family rates after {pages_fetched}"
                        f" pages — stopping pagination"
                    )
                    break

                next_page_token = payload.get("nextPageToken")
                if not next_page_token:
                    break

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            if status_code == 403:
                logger.error(
                    "Failed to fetch GCP pricing for %s: %s. "
                    "Ensure the Cloud Billing API is enabled "
                    "in the GCP project: "
                    "https://console.cloud.google.com/apis/"
                    "library/cloudbilling.googleapis.com",
                    region,
                    e,
                )
                return []
            else:
                logger.warning(
                    f"Failed to fetch GCP pricing for "
                    f"{region}: {e}. Using partial data "
                    f"({len(core_rates)} core rates, "
                    f"{len(ram_rates)} ram rates collected "
                    f"before error)."
                )
        except Exception as e:
            logger.warning(
                f"Failed to fetch GCP pricing for "
                f"{region}: {e}. Using partial data "
                f"({len(core_rates)} core rates, "
                f"{len(ram_rates)} ram rates collected "
                f"before error)."
            )

        if not instance_types:
            logger.info(
                "No discovered GCP instance types for "
                f"{region}; skipping compute synthesis"
            )
            return []

        pricing_data: List[Dict] = []
        for instance_type in instance_types:
            rate = self._calculate_gcp_machine_hourly_rate(
                instance_type=instance_type,
                core_rates=core_rates,
                ram_rates=ram_rates,
            )
            if rate is None or rate <= 0:
                continue

            pricing_data.append(
                {
                    "provider_type": "gcp",
                    "region": region,
                    "instance_type": instance_type,
                    "hourly_rate": rate,
                    "last_updated": datetime.now(timezone.utc),
                }
            )

        logger.info(
            f"Found {len(pricing_data)} GCP pricing records for {region}"
        )
        return pricing_data

    def fetch_pricing(
        self,
        provider_type: str,
        region_code: str,
        instance_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Provider-aware pricing fetch dispatcher."""
        provider = provider_type.lower()
        if provider == "aws":
            return self.fetch_aws_pricing(region_code)
        if provider == "azure":
            return self.fetch_azure_pricing(region_code)
        if provider == "gcp":
            return self.fetch_gcp_pricing(region_code, instance_types=instance_types)

        logger.warning(f"Pricing fetch not implemented for provider '{provider_type}'")
        return []

    async def update_pricing_db(
        self,
        region_codes: List[str],
        provider_type: str = "aws",
    ):
        """Update the database with fresh pricing data for one provider."""
        total_updated = 0

        # For GCP, deduplicate zones to regions (e.g.
        # us-central1-a,b,c,f all map to us-central1)
        # to avoid fetching the same pricing data multiple
        # times.
        if provider_type.lower() == "gcp":
            seen_regions: set[str] = set()
            deduped: List[str] = []
            for r in region_codes:
                norm = self._normalize_gcp_region(r)
                if norm not in seen_regions:
                    seen_regions.add(norm)
                    deduped.append(r)
            if len(deduped) < len(region_codes):
                logger.info(
                    f"Deduplicated {len(region_codes)} GCP "
                    f"zones to {len(deduped)} regions"
                )
            region_codes = deduped

        for region in region_codes:
            gcp_instance_types = None
            if provider_type.lower() == "gcp":
                gcp_instance_types = await self._get_gcp_instance_types_for_region(
                    self._normalize_gcp_region(region)
                )
            data = await asyncio.to_thread(
                self.fetch_pricing,
                provider_type,
                region,
                gcp_instance_types,
            )
            if not data:
                continue

            # Batch upsert
            # We use chunks to avoid overwhelming the DB
            chunk_size = 1000
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]

                stmt = insert(InstancePricing).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['provider_type', 'region', 'instance_type'],
                    set_={
                        'hourly_rate': stmt.excluded.hourly_rate,
                        'last_updated': stmt.excluded.last_updated
                    }
                )

                await self.db.execute(stmt)

            total_updated += len(data)
            logger.info(
                f"Updated {len(data)} pricing records for "
                f"{provider_type}:{region}"
            )

        await self.db.commit()
        return total_updated
