"""Tests for API key schema computed fields and default expiry."""

import uuid
from datetime import datetime, timedelta, timezone

from app.schemas.apikey import APIKeyShow, DEFAULT_KEY_EXPIRY_DAYS


class TestAPIKeyShowComputedFields:
    def _make_key(self, expires_at=None):
        return APIKeyShow(
            id=uuid.uuid4(),
            name="test",
            prefix="abcd1234",
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

    def test_no_expiration_days_until_is_none(self):
        key = self._make_key(expires_at=None)
        assert key.days_until_expiry is None

    def test_no_expiration_expires_soon_is_false(self):
        key = self._make_key(expires_at=None)
        assert key.expires_soon is False

    def test_expires_in_30_days_not_soon(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        assert key.days_until_expiry == 29  # timedelta(days=30) is ~29.999 days
        assert key.expires_soon is False

    def test_expires_in_7_days_is_soon(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        assert key.days_until_expiry <= 7
        assert key.expires_soon is True

    def test_expires_in_3_days_is_soon(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=3)
        )
        assert key.days_until_expiry <= 3
        assert key.expires_soon is True

    def test_expires_in_1_day_is_soon(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        assert key.days_until_expiry <= 1
        assert key.expires_soon is True

    def test_already_expired_days_is_zero(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        assert key.days_until_expiry == 0

    def test_expires_in_10_days_not_soon(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=10)
        )
        assert key.expires_soon is False

    def test_computed_fields_in_serialization(self):
        key = self._make_key(
            expires_at=datetime.now(timezone.utc) + timedelta(days=3)
        )
        data = key.model_dump()
        assert "days_until_expiry" in data
        assert "expires_soon" in data
        assert data["expires_soon"] is True


class TestDefaultExpiryConstant:
    def test_default_expiry_is_90_days(self):
        assert DEFAULT_KEY_EXPIRY_DAYS == 90
