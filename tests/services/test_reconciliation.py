import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from app.providers.models import InstanceState
from app.services.reconciliation import ReconciliationService
from tests.services.conftest import make_result

_DECRYPT = "app.services.reconciliation.decrypt_credentials"
_BUILD = "app.services.reconciliation.build_credentials"
_GET_PROV = "app.services.reconciliation.get_provider"
_TO_THREAD = "app.services.reconciliation.asyncio.to_thread"
_FAKE_CREDS = {"access_key_id": "x", "secret_access_key": "y", "region": "us-east-1"}


def _resource(state="STOPPED"):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.state = state
    r.cloud_account_id = uuid.uuid4()
    r.organization_id = uuid.uuid4()
    r.provider_resource_id = "i-123"
    r.region = "us-east-1"
    return r


def _cloud_account():
    return SimpleNamespace(
        id=uuid.uuid4(),
        provider_type="aws",
        credentials_encrypted="encrypted",
    )


class TestReconcileResource:
    def _svc(self, mock_db):
        svc = ReconciliationService(db=mock_db)
        # Replace policy_engine with an AsyncMock so get_desired_state is controllable
        svc.policy_engine = AsyncMock()
        return svc

    async def test_no_action_needed(self, mock_db):
        svc = self._svc(mock_db)
        resource = _resource(state="RUNNING")
        svc.policy_engine.get_desired_state = AsyncMock(return_value=InstanceState.RUNNING)
        assert await svc.reconcile_resource(resource) is False

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_start_success(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        resource = _resource(state="STOPPED")
        svc.policy_engine.get_desired_state = AsyncMock(return_value=InstanceState.RUNNING)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=_cloud_account()))

        with patch(_TO_THREAD, new=AsyncMock(return_value=True)):
            result = await svc.reconcile_resource(resource)

        assert result is True
        from app.models.execution import Execution
        from app.models.resource_state_event import ResourceStateEvent
        added = [c[0][0] for c in mock_db.add.call_args_list]
        execs = [o for o in added if isinstance(o, Execution)]
        events = [o for o in added if isinstance(o, ResourceStateEvent)]
        assert len(execs) == 1
        assert execs[0].action == "START"
        assert execs[0].success is True
        assert len(events) == 1

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_stop_success(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        resource = _resource(state="RUNNING")
        svc.policy_engine.get_desired_state = AsyncMock(return_value=InstanceState.STOPPED)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=_cloud_account()))

        with patch(_TO_THREAD, new=AsyncMock(return_value=True)):
            result = await svc.reconcile_resource(resource)

        assert result is True
        from app.models.execution import Execution
        added = [c[0][0] for c in mock_db.add.call_args_list]
        execs = [o for o in added if isinstance(o, Execution)]
        assert execs[0].action == "STOP"
        assert execs[0].success is True

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_provider_exception_logs_failure(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        resource = _resource(state="STOPPED")
        svc.policy_engine.get_desired_state = AsyncMock(return_value=InstanceState.RUNNING)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=_cloud_account()))

        with patch(_TO_THREAD, new=AsyncMock(side_effect=Exception("timeout"))):
            result = await svc.reconcile_resource(resource)

        assert result is True
        from app.models.execution import Execution
        from app.models.resource_state_event import ResourceStateEvent
        added = [c[0][0] for c in mock_db.add.call_args_list]
        execs = [o for o in added if isinstance(o, Execution)]
        events = [o for o in added if isinstance(o, ResourceStateEvent)]
        assert execs[0].success is False
        assert execs[0].error_message == "timeout"
        assert len(events) == 0  # no state event on failure
