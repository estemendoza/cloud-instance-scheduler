import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.cost_calculator import CostCalculator
from tests.services.conftest import make_result


def _resource(id=None, instance_type="t3.micro", cloud_account_id=None,
              organization_id=None, region="us-east-1", tags=None):
    return SimpleNamespace(
        id=id or uuid.uuid4(),
        instance_type=instance_type,
        cloud_account_id=cloud_account_id or uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        region=region,
        tags=tags or {},
    )


def _cloud_account(provider_type="aws"):
    return SimpleNamespace(provider_type=provider_type)


def _pricing(rate=Decimal("0.1")):
    return SimpleNamespace(hourly_rate=rate)


def _policy(schedule=None, selector=None):
    return SimpleNamespace(
        name="Test Policy",
        schedule=schedule or {
            day: [{"start": "09:00", "end": "17:00"}]
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
        },
        resource_selector=selector or {"tags": {"env": "test"}},
    )


class TestCalculateResourceSavings:
    def _calc(self, mock_db):
        return CostCalculator(db=mock_db)

    async def test_resource_not_found(self, mock_db):
        calc = self._calc(mock_db)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=None))
        result = await calc.calculate_resource_savings(uuid.uuid4())
        assert result["monthly_savings"] == 0.0
        assert "not found" in result["note"]

    async def test_no_instance_type(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource(instance_type=None)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=resource))
        result = await calc.calculate_resource_savings(resource.id)
        assert result["monthly_savings"] == 0.0
        assert "No instance type" in result["note"]

    async def test_cloud_account_not_found(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=None),  # CloudAccount
        ])
        result = await calc.calculate_resource_savings(resource.id)
        assert "Cloud account not found" in result["note"]

    async def test_no_pricing(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_cloud_account()),
            make_result(scalar=None),  # InstancePricing
        ])
        result = await calc.calculate_resource_savings(resource.id)
        assert "Pricing not available" in result["note"]

    async def test_no_applicable_policy(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_cloud_account()),
            make_result(scalar=_pricing()),
            make_result(scalars=[]),  # empty policy list
        ])
        result = await calc.calculate_resource_savings(resource.id)
        assert result["hourly_rate"] == 0.1
        assert result["monthly_savings"] == 0.0
        assert "No active policy" in result["note"]

    async def test_happy_path_math(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource(tags={"env": "test"})
        policy = _policy()  # Mon-Fri 9-17 → 128 stopped h/week
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_cloud_account()),
            make_result(scalar=_pricing(Decimal("0.1"))),
            make_result(scalars=[policy]),
        ])
        result = await calc.calculate_resource_savings(resource.id)
        # 128 h × $0.10 × 4.33 weeks = $55.424 → round → 55.42
        assert result["monthly_savings"] == 55.42
        # 55.424 × 12 = 665.088 → round → 665.09
        assert result["annual_savings"] == 665.09
        assert result["policy_name"] == "Test Policy"

    async def test_gcp_zone_fallbacks_to_region_pricing(self, mock_db):
        calc = self._calc(mock_db)
        resource = _resource(region="us-east1-b", tags={"env": "test"})
        policy = _policy()

        # First pricing lookup (zone) misses, second (normalized region) hits.
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_cloud_account(provider_type="gcp")),
            make_result(scalar=None),
            make_result(scalar=_pricing(Decimal("0.1"))),
            make_result(scalars=[policy]),
        ])

        result = await calc.calculate_resource_savings(resource.id)
        assert result["hourly_rate"] == 0.1
        assert result["monthly_savings"] == 55.42
