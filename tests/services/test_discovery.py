import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.models import InstanceInfo, InstanceState
from app.services.discovery import DiscoveryService
from tests.services.conftest import make_result


def _cloud_account(id=None, org_id=None, is_active=True):
    return SimpleNamespace(
        id=id or uuid.uuid4(),
        organization_id=org_id or uuid.uuid4(),
        is_active=is_active,
        provider_type="aws",
        credentials_encrypted="encrypted",
        selected_regions=None,
    )


def _instance(id="i-123", state=InstanceState.RUNNING):
    return InstanceInfo(
        id=id, name="test", state=state, tags={},
        region="us-east-1", provider="aws", instance_type="t3.micro",
    )


def _existing(state="RUNNING"):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.state = state
    r.name = "existing"
    r.tags = {}
    r.instance_type = "t3.micro"
    r.region = "us-east-1"
    return r


# Common patches applied to every test in this module
_DECRYPT = "app.services.discovery.decrypt_credentials"
_BUILD = "app.services.discovery.build_credentials"
_GET_PROV = "app.services.discovery.get_provider"
_TO_THREAD = "app.services.discovery.asyncio.to_thread"
_FAKE_CREDS = {"access_key_id": "x", "secret_access_key": "y", "region": "us-east-1"}


class TestSyncResources:
    def _svc(self, mock_db):
        return DiscoveryService(db=mock_db)

    async def test_account_not_found(self, mock_db):
        svc = self._svc(mock_db)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=None))
        assert await svc.sync_resources(uuid.uuid4()) == {"created": 0, "updated": 0, "total": 0}

    async def test_account_inactive(self, mock_db):
        svc = self._svc(mock_db)
        account = _cloud_account(is_active=False)
        mock_db.execute = AsyncMock(return_value=make_result(scalar=account))
        assert await svc.sync_resources(account.id) == {"created": 0, "updated": 0, "total": 0}

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_all_new(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        account = _cloud_account()
        instances = [_instance(id=f"i-{i}") for i in range(3)]
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=account),
            make_result(scalar=None),   # i-0 not existing
            make_result(scalar=None),   # i-1
            make_result(scalar=None),   # i-2
        ])
        with patch(_TO_THREAD, new=AsyncMock(return_value=instances)):
            result = await svc.sync_resources(account.id)

        assert result == {"created": 3, "updated": 0, "total": 3}
        assert mock_db.add.call_count == 3

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_all_existing_updated(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        account = _cloud_account()
        instances = [_instance(id="i-0", state=InstanceState.RUNNING)]
        existing = _existing(state="RUNNING")
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=account),
            make_result(scalar=existing),
        ])
        with patch(_TO_THREAD, new=AsyncMock(return_value=instances)):
            result = await svc.sync_resources(account.id)

        assert result == {"created": 0, "updated": 1, "total": 1}

    @patch(_DECRYPT, return_value=_FAKE_CREDS)
    @patch(_BUILD)
    @patch(_GET_PROV)
    async def test_state_change_creates_event(self, mock_prov, mock_build, mock_decrypt, mock_db):
        svc = self._svc(mock_db)
        account = _cloud_account()
        # Provider says RUNNING; DB has STOPPED → state change
        instances = [_instance(id="i-0", state=InstanceState.RUNNING)]
        existing = _existing(state="STOPPED")
        mock_db.execute = AsyncMock(side_effect=[
            make_result(scalar=account),
            make_result(scalar=existing),
        ])
        with patch(_TO_THREAD, new=AsyncMock(return_value=instances)):
            await svc.sync_resources(account.id)

        from app.models.resource_state_event import ResourceStateEvent
        added = [call[0][0] for call in mock_db.add.call_args_list]
        events = [o for o in added if isinstance(o, ResourceStateEvent)]
        assert len(events) == 1
        assert events[0].previous_state == "STOPPED"
        assert events[0].new_state == "RUNNING"
        assert events[0].source == "discovery"
