import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from google.api_core.exceptions import GoogleAPIError, Forbidden, NotFound

from app.providers.models import GCPCredentials, InstanceState
from app.providers.gcp_compute import GCPComputeProvider


_SA_JSON = '{"type":"service_account","project_id":"test","private_key_id":"k"}'


@pytest.fixture
def mock_instances_client():
    """Patch GCP InstancesClient; yield the mock."""
    mock_client = MagicMock()
    with patch(
        "app.providers.gcp_compute.compute_v1.InstancesClient",
        return_value=mock_client,
    ), patch(
        "app.providers.gcp_compute.service_account.Credentials"
        ".from_service_account_info",
    ):
        yield mock_client


@pytest.fixture
def gcp_provider(mock_instances_client):
    """GCPComputeProvider wired to the mocked instances client."""
    creds = GCPCredentials(
        project_id="my-project",
        service_account_json=_SA_JSON,
    )
    return GCPComputeProvider(creds)


def _make_instance(name="inst-1", zone="us-east1-b", status="RUNNING",
                   labels=None, machine_type=None):
    """Create a mock GCP instance object."""
    inst = MagicMock()
    inst.name = name
    inst.status = status
    inst.labels = labels
    inst.machine_type = machine_type or (
        f"projects/my-project/zones/{zone}/machineTypes/e2-medium"
    )
    return inst


def _make_zone_response(instances):
    """Create a mock zone-scoped list response."""
    resp = MagicMock()
    resp.instances = instances
    return resp


# ── Validate Credentials ──────────────────────────────────────


class TestValidateCredentials:
    def test_validate_success(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.return_value = iter([])
        result = gcp_provider.validate_credentials()
        assert result.is_valid is True

    def test_validate_forbidden(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.side_effect = (
            Forbidden("no access")
        )
        result = gcp_provider.validate_credentials()
        assert result.is_valid is False
        assert "permissions" in result.error_message

    def test_validate_api_error(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.side_effect = (
            GoogleAPIError("api down")
        )
        result = gcp_provider.validate_credentials()
        assert result.is_valid is False
        assert "validation failed" in result.error_message

    def test_validate_generic_error(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.side_effect = (
            Exception("unexpected")
        )
        result = gcp_provider.validate_credentials()
        assert result.is_valid is False
        assert "unexpected" in result.error_message

    def test_validate_invalid_json(self):
        """Invalid service account JSON triggers JSONDecodeError."""
        with patch(
            "app.providers.gcp_compute.service_account.Credentials"
            ".from_service_account_info",
        ), patch(
            "app.providers.gcp_compute.compute_v1.InstancesClient",
        ) as mock_cls:
            # Make aggregated_list raise during JSON parsing
            import json
            mock_cls.return_value.aggregated_list.side_effect = (
                json.JSONDecodeError("bad", "", 0)
            )
            creds = GCPCredentials(
                project_id="p", service_account_json="not-json",
            )
            provider = GCPComputeProvider(creds)
            result = provider.validate_credentials()
            assert result.is_valid is False
            assert "Invalid service account JSON" in result.error_message


# ── List Instances ─────────────────────────────────────────────


class TestListInstances:
    def test_list_all_zones(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([
                _make_instance("inst-1", "us-east1-b"),
            ])),
            ("zones/us-west1-a", _make_zone_response([
                _make_instance("inst-2", "us-west1-a"),
            ])),
        ])

        result = gcp_provider.list_instances()
        assert len(result) == 2
        assert result[0].provider == "gcp"
        assert result[0].id == "inst-1"
        assert result[0].region == "us-east1-b"
        assert result[1].region == "us-west1-a"

    def test_list_with_zone_filter(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([
                _make_instance("inst-1"),
            ])),
            ("zones/us-west1-a", _make_zone_response([
                _make_instance("inst-2"),
            ])),
        ])

        result = gcp_provider.list_instances(regions=["us-east1-b"])
        assert len(result) == 1
        assert result[0].id == "inst-1"

    def test_list_extracts_labels(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([
                _make_instance("inst-1", labels={"env": "prod", "name": "web"}),
            ])),
        ])

        result = gcp_provider.list_instances()
        assert result[0].tags == {"env": "prod", "name": "web"}
        assert result[0].name == "web"

    def test_list_no_labels(self, gcp_provider, mock_instances_client):
        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([
                _make_instance("inst-1", labels=None),
            ])),
        ])

        result = gcp_provider.list_instances()
        assert result[0].tags == {}
        # Falls back to instance name
        assert result[0].name == "inst-1"

    def test_list_skips_empty_zones(self, gcp_provider, mock_instances_client):
        empty_resp = MagicMock()
        empty_resp.instances = None

        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", empty_resp),
            ("zones/us-west1-a", _make_zone_response([
                _make_instance("inst-1"),
            ])),
        ])

        result = gcp_provider.list_instances()
        assert len(result) == 1

    def test_list_api_error_returns_empty(
        self, gcp_provider, mock_instances_client
    ):
        mock_instances_client.aggregated_list.side_effect = (
            GoogleAPIError("network")
        )
        result = gcp_provider.list_instances()
        assert result == []

    def test_list_extracts_machine_type(
        self, gcp_provider, mock_instances_client
    ):
        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([
                _make_instance(
                    "inst-1",
                    machine_type="projects/p/zones/z/machineTypes/n2-standard-4"
                ),
            ])),
        ])

        result = gcp_provider.list_instances()
        assert result[0].instance_type == "n2-standard-4"

    def test_list_instance_error_skips(
        self, gcp_provider, mock_instances_client
    ):
        """If one instance fails, others are still returned."""
        bad_inst = MagicMock()
        bad_inst.name = "bad"
        bad_inst.status = "RUNNING"
        bad_inst.labels = None
        # machine_type that causes an error when accessed
        type(bad_inst).machine_type = PropertyMock(side_effect=Exception("oops"))

        good_inst = _make_instance("good")

        mock_instances_client.aggregated_list.return_value = iter([
            ("zones/us-east1-b", _make_zone_response([bad_inst, good_inst])),
        ])

        result = gcp_provider.list_instances()
        assert len(result) == 1
        assert result[0].id == "good"


# ── Get Instance State ─────────────────────────────────────────


class TestGetInstanceState:
    def test_get_state_running(self, gcp_provider, mock_instances_client):
        inst = MagicMock()
        inst.status = "RUNNING"
        mock_instances_client.get.return_value = inst

        assert gcp_provider.get_instance_state(
            "inst-1", "us-east1-b"
        ) == InstanceState.RUNNING
        mock_instances_client.get.assert_called_once_with(
            project="my-project", zone="us-east1-b", instance="inst-1"
        )

    def test_get_state_stopped(self, gcp_provider, mock_instances_client):
        inst = MagicMock()
        inst.status = "STOPPED"
        mock_instances_client.get.return_value = inst

        assert gcp_provider.get_instance_state(
            "inst-1", "us-east1-b"
        ) == InstanceState.STOPPED

    def test_get_state_terminated(self, gcp_provider, mock_instances_client):
        inst = MagicMock()
        inst.status = "TERMINATED"
        mock_instances_client.get.return_value = inst

        assert gcp_provider.get_instance_state(
            "inst-1", "us-east1-b"
        ) == InstanceState.STOPPED

    def test_get_state_not_found(self, gcp_provider, mock_instances_client):
        mock_instances_client.get.side_effect = NotFound("gone")
        assert gcp_provider.get_instance_state(
            "inst-1", "us-east1-b"
        ) == InstanceState.UNKNOWN

    def test_get_state_api_error(self, gcp_provider, mock_instances_client):
        mock_instances_client.get.side_effect = GoogleAPIError("err")
        assert gcp_provider.get_instance_state(
            "inst-1", "us-east1-b"
        ) == InstanceState.UNKNOWN


# ── Start Instance ─────────────────────────────────────────────


class TestStartInstance:
    def test_start_success(self, gcp_provider, mock_instances_client):
        operation = MagicMock()
        mock_instances_client.start.return_value = operation
        assert gcp_provider.start_instance("inst-1", "us-east1-b") is True
        mock_instances_client.start.assert_called_once_with(
            project="my-project", zone="us-east1-b", instance="inst-1"
        )
        operation.result.assert_called_once()

    def test_start_already_running(self, gcp_provider, mock_instances_client):
        mock_instances_client.start.side_effect = (
            GoogleAPIError("Instance is already running")
        )
        assert gcp_provider.start_instance("inst-1", "us-east1-b") is True

    def test_start_error_raises(self, gcp_provider, mock_instances_client):
        mock_instances_client.start.side_effect = (
            GoogleAPIError("quota exceeded")
        )
        with pytest.raises(GoogleAPIError):
            gcp_provider.start_instance("inst-1", "us-east1-b")


# ── Stop Instance ──────────────────────────────────────────────


class TestStopInstance:
    def test_stop_success(self, gcp_provider, mock_instances_client):
        operation = MagicMock()
        mock_instances_client.stop.return_value = operation
        assert gcp_provider.stop_instance("inst-1", "us-east1-b") is True
        mock_instances_client.stop.assert_called_once_with(
            project="my-project", zone="us-east1-b", instance="inst-1"
        )
        operation.result.assert_called_once()

    def test_stop_already_stopped(self, gcp_provider, mock_instances_client):
        mock_instances_client.stop.side_effect = (
            GoogleAPIError("Instance is already stopped")
        )
        assert gcp_provider.stop_instance("inst-1", "us-east1-b") is True

    def test_stop_error_raises(self, gcp_provider, mock_instances_client):
        mock_instances_client.stop.side_effect = (
            GoogleAPIError("permission denied")
        )
        with pytest.raises(GoogleAPIError):
            gcp_provider.stop_instance("inst-1", "us-east1-b")


# ── Normalize State ────────────────────────────────────────────


class TestNormalizeState:
    @pytest.mark.parametrize("gcp_status,expected", [
        ("RUNNING", InstanceState.RUNNING),
        ("PROVISIONING", InstanceState.RUNNING),
        ("STAGING", InstanceState.RUNNING),
        ("STOPPED", InstanceState.STOPPED),
        ("TERMINATED", InstanceState.STOPPED),
        ("SUSPENDED", InstanceState.STOPPED),
        ("STOPPING", InstanceState.STOPPED),
        ("SUSPENDING", InstanceState.STOPPED),
        ("SOMETHING_ELSE", InstanceState.UNKNOWN),
        (None, InstanceState.UNKNOWN),
    ])
    def test_normalize(self, gcp_provider, gcp_status, expected):
        assert gcp_provider._normalize_state(gcp_status) == expected


# ── Extract Machine Type ──────────────────────────────────────


class TestExtractMachineType:
    def test_full_url(self, gcp_provider):
        url = "projects/p/zones/us-east1-b/machineTypes/e2-medium"
        assert gcp_provider._extract_machine_type(url) == "e2-medium"

    def test_none(self, gcp_provider):
        assert gcp_provider._extract_machine_type(None) is None

    def test_just_name(self, gcp_provider):
        assert gcp_provider._extract_machine_type("n1-standard-1") == "n1-standard-1"
