import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.providers.models import InstanceState
from app.services.policy_engine import PolicyEngine
from tests.services.conftest import make_result


def _resource(org_id=None, id=None, tags=None):
    return SimpleNamespace(
        id=id or uuid.uuid4(),
        organization_id=org_id or uuid.uuid4(),
        tags=tags or {},
    )


def _override(desired_state="RUNNING"):
    return SimpleNamespace(desired_state=desired_state)


def _policy():
    return SimpleNamespace(
        schedule={"monday": [{"start": "09:00", "end": "17:00"}]},
        timezone="UTC",
        schedule_type="weekly",
        resource_selector={"tags": {"env": "test"}},
    )


class TestGetDesiredState:
    # ── helper ────────────────────────────────────────────────────

    def _make_engine(self, mock_db):
        return PolicyEngine(db=mock_db)

    # ── tests ─────────────────────────────────────────────────────

    async def test_resource_not_found(self, mock_db):
        engine = self._make_engine(mock_db)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=None))
        assert await engine.get_desired_state(uuid.uuid4(), datetime.now(timezone.utc)) == InstanceState.STOPPED

    async def test_active_override_running(self, mock_db):
        engine = self._make_engine(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_override("RUNNING")),
        ])
        assert await engine.get_desired_state(resource.id, datetime.now(timezone.utc)) == InstanceState.RUNNING

    async def test_active_override_stopped(self, mock_db):
        engine = self._make_engine(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=_override("STOPPED")),
        ])
        assert await engine.get_desired_state(resource.id, datetime.now(timezone.utc)) == InstanceState.STOPPED

    async def test_no_override_policy_running(self, mock_db):
        engine = self._make_engine(mock_db)
        resource = _resource(tags={"env": "test"})
        policy = _policy()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=None),       # no active override
            make_result(scalars=[policy]),
        ])
        with patch.object(engine.schedule_evaluator, "is_running_time", return_value=True):
            with patch.object(engine, "_policy_applies_to_resource", return_value=True):
                result = await engine.get_desired_state(resource.id, datetime.now(timezone.utc))
        assert result == InstanceState.RUNNING

    async def test_no_override_policy_outside_window(self, mock_db):
        engine = self._make_engine(mock_db)
        resource = _resource(tags={"env": "test"})
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=None),
            make_result(scalars=[_policy()]),
        ])
        with patch.object(engine.schedule_evaluator, "is_running_time", return_value=False):
            with patch.object(engine, "_policy_applies_to_resource", return_value=True):
                result = await engine.get_desired_state(resource.id, datetime.now(timezone.utc))
        assert result == InstanceState.STOPPED

    async def test_no_override_no_policies(self, mock_db):
        engine = self._make_engine(mock_db)
        resource = _resource()
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=None),
            make_result(scalars=[]),
        ])
        assert await engine.get_desired_state(resource.id, datetime.now(timezone.utc)) == InstanceState.STOPPED

    async def test_expired_override_falls_through(self, mock_db):
        """Expired overrides are filtered by the DB query; mock returns None."""
        engine = self._make_engine(mock_db)
        resource = _resource(tags={"env": "test"})
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=resource),
            make_result(scalar=None),       # expired override filtered out
            make_result(scalars=[_policy()]),
        ])
        with patch.object(engine.schedule_evaluator, "is_running_time", return_value=True):
            with patch.object(engine, "_policy_applies_to_resource", return_value=True):
                result = await engine.get_desired_state(resource.id, datetime.now(timezone.utc))
        assert result == InstanceState.RUNNING
