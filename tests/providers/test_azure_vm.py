import pytest
from unittest.mock import patch, MagicMock

from azure.core.exceptions import AzureError, ClientAuthenticationError

from app.providers.models import AzureCredentials, InstanceState
from app.providers.azure_vm import AzureVMProvider


@pytest.fixture
def mock_compute_client():
    """Patch Azure ComputeManagementClient; yield the mock."""
    mock_client = MagicMock()
    with patch(
        "app.providers.azure_vm.ComputeManagementClient",
        return_value=mock_client,
    ), patch(
        "app.providers.azure_vm.ClientSecretCredential",
    ):
        yield mock_client


@pytest.fixture
def azure_provider(mock_compute_client):
    """AzureVMProvider wired to the mocked compute client."""
    creds = AzureCredentials(
        subscription_id="sub-123",
        tenant_id="tenant-123",
        client_id="client-123",
        client_secret="secret",
    )
    return AzureVMProvider(creds)


def _make_vm(name="vm-1", location="eastus", vm_id=None, tags=None,
             vm_size="Standard_B2s"):
    """Create a mock Azure VM object."""
    vm = MagicMock()
    vm.name = name
    vm.location = location
    vm.id = vm_id or (
        f"/subscriptions/sub-123/resourceGroups/rg-1"
        f"/providers/Microsoft.Compute/virtualMachines/{name}"
    )
    vm.tags = tags
    vm.hardware_profile = MagicMock()
    vm.hardware_profile.vm_size = vm_size
    return vm


def _make_instance_view(*power_states):
    """Create a mock instance view with the given power state codes."""
    view = MagicMock()
    statuses = []
    for code in power_states:
        s = MagicMock()
        s.code = code
        statuses.append(s)
    view.statuses = statuses
    return view


# ── Validate Credentials ──────────────────────────────────────


class TestValidateCredentials:
    def test_validate_success(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = []
        result = azure_provider.validate_credentials()
        assert result.is_valid is True

    def test_validate_auth_error(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.side_effect = (
            ClientAuthenticationError("bad creds")
        )
        result = azure_provider.validate_credentials()
        assert result.is_valid is False
        assert "authentication failed" in result.error_message

    def test_validate_azure_error(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.side_effect = (
            AzureError("network issue")
        )
        result = azure_provider.validate_credentials()
        assert result.is_valid is False
        assert "validation failed" in result.error_message

    def test_validate_generic_error(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.side_effect = (
            Exception("unexpected")
        )
        result = azure_provider.validate_credentials()
        assert result.is_valid is False
        assert "unexpected" in result.error_message


# ── List Instances ─────────────────────────────────────────────


class TestListInstances:
    def test_list_all(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = [
            _make_vm("vm-1", "eastus"),
            _make_vm("vm-2", "westus"),
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("ProvisioningState/succeeded",
                                "PowerState/running")
        )

        result = azure_provider.list_instances()
        assert len(result) == 2
        assert result[0].provider == "azure"
        assert result[0].id == "rg-1/vm-1"
        assert result[1].id == "rg-1/vm-2"

    def test_list_with_region_filter(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = [
            _make_vm("vm-east", "eastus"),
            _make_vm("vm-west", "westus"),
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/running")
        )

        result = azure_provider.list_instances(regions=["eastus"])
        assert len(result) == 1
        assert result[0].name == "vm-east"

    def test_list_extracts_tags(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = [
            _make_vm("vm-1", tags={"env": "prod", "Name": "web-1"}),
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/running")
        )

        result = azure_provider.list_instances()
        assert result[0].tags == {"env": "prod", "Name": "web-1"}
        assert result[0].name == "web-1"

    def test_list_no_tags(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = [
            _make_vm("vm-1", tags=None),
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/stopped")
        )

        result = azure_provider.list_instances()
        assert result[0].tags == {}
        # Falls back to VM name when no Name tag
        assert result[0].name == "vm-1"

    def test_list_azure_error_returns_empty(
        self, azure_provider, mock_compute_client
    ):
        mock_compute_client.virtual_machines.list_all.side_effect = (
            AzureError("network")
        )
        result = azure_provider.list_instances()
        assert result == []

    def test_list_vm_processing_error_skips(
        self, azure_provider, mock_compute_client
    ):
        """If one VM fails to process, others are still returned."""
        good_vm = _make_vm("vm-good", "eastus")
        bad_vm = _make_vm("vm-bad", "eastus")
        # Bad VM has an ID that can't be parsed for resource group
        bad_vm.id = "invalid-id-no-slashes"

        mock_compute_client.virtual_machines.list_all.return_value = [
            bad_vm, good_vm
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/running")
        )

        result = azure_provider.list_instances()
        assert len(result) == 1
        assert result[0].id == "rg-1/vm-good"

    def test_list_instance_type(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.list_all.return_value = [
            _make_vm("vm-1", vm_size="Standard_D4s_v3"),
        ]
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/running")
        )

        result = azure_provider.list_instances()
        assert result[0].instance_type == "Standard_D4s_v3"


# ── Get Instance State ─────────────────────────────────────────


class TestGetInstanceState:
    def test_get_state_running(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("ProvisioningState/succeeded",
                                "PowerState/running")
        )
        assert azure_provider.get_instance_state(
            "rg-1/vm-1", "eastus"
        ) == InstanceState.RUNNING

    def test_get_state_deallocated(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/deallocated")
        )
        assert azure_provider.get_instance_state(
            "rg-1/vm-1", "eastus"
        ) == InstanceState.STOPPED

    def test_get_state_stopped(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("PowerState/stopped")
        )
        assert azure_provider.get_instance_state(
            "rg-1/vm-1", "eastus"
        ) == InstanceState.STOPPED

    def test_get_state_invalid_id(self, azure_provider, mock_compute_client):
        """Invalid instance ID format returns UNKNOWN."""
        assert azure_provider.get_instance_state(
            "no-slash", "eastus"
        ) == InstanceState.UNKNOWN

    def test_get_state_azure_error(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.instance_view.side_effect = (
            AzureError("not found")
        )
        assert azure_provider.get_instance_state(
            "rg-1/vm-1", "eastus"
        ) == InstanceState.UNKNOWN

    def test_get_state_no_power_state(self, azure_provider, mock_compute_client):
        """Instance view with no PowerState returns UNKNOWN."""
        mock_compute_client.virtual_machines.instance_view.return_value = (
            _make_instance_view("ProvisioningState/succeeded")
        )
        assert azure_provider.get_instance_state(
            "rg-1/vm-1", "eastus"
        ) == InstanceState.UNKNOWN


# ── Start Instance ─────────────────────────────────────────────


class TestStartInstance:
    def test_start_success(self, azure_provider, mock_compute_client):
        poller = MagicMock()
        mock_compute_client.virtual_machines.begin_start.return_value = poller
        assert azure_provider.start_instance("rg-1/vm-1", "eastus") is True
        mock_compute_client.virtual_machines.begin_start.assert_called_once_with(
            resource_group_name="rg-1", vm_name="vm-1"
        )
        poller.result.assert_called_once()

    def test_start_already_running(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.begin_start.side_effect = (
            AzureError("VM is already running")
        )
        assert azure_provider.start_instance("rg-1/vm-1", "eastus") is True

    def test_start_error_raises(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.begin_start.side_effect = (
            AzureError("quota exceeded")
        )
        with pytest.raises(AzureError):
            azure_provider.start_instance("rg-1/vm-1", "eastus")

    def test_start_invalid_id_raises(self, azure_provider):
        with pytest.raises(ValueError, match="Invalid Azure instance ID"):
            azure_provider.start_instance("no-slash", "eastus")


# ── Stop Instance ──────────────────────────────────────────────


class TestStopInstance:
    def test_stop_success(self, azure_provider, mock_compute_client):
        poller = MagicMock()
        mock_compute_client.virtual_machines.begin_deallocate.return_value = (
            poller
        )
        assert azure_provider.stop_instance("rg-1/vm-1", "eastus") is True
        mock_compute_client.virtual_machines.begin_deallocate.assert_called_once_with(
            resource_group_name="rg-1", vm_name="vm-1"
        )
        poller.result.assert_called_once()

    def test_stop_already_deallocated(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.begin_deallocate.side_effect = (
            AzureError("VM is already deallocated")
        )
        assert azure_provider.stop_instance("rg-1/vm-1", "eastus") is True

    def test_stop_error_raises(self, azure_provider, mock_compute_client):
        mock_compute_client.virtual_machines.begin_deallocate.side_effect = (
            AzureError("permission denied")
        )
        with pytest.raises(AzureError):
            azure_provider.stop_instance("rg-1/vm-1", "eastus")


# ── Normalize State ────────────────────────────────────────────


class TestNormalizeState:
    @pytest.mark.parametrize("power_state,expected", [
        ("PowerState/running", InstanceState.RUNNING),
        ("PowerState/starting", InstanceState.RUNNING),
        ("PowerState/stopped", InstanceState.STOPPED),
        ("PowerState/deallocated", InstanceState.STOPPED),
        ("PowerState/deallocating", InstanceState.STOPPED),
        ("PowerState/stopping", InstanceState.STOPPED),
        ("PowerState/poweredoff", InstanceState.STOPPED),
        ("PowerState/unknown", InstanceState.UNKNOWN),
        (None, InstanceState.UNKNOWN),
    ])
    def test_normalize(self, azure_provider, power_state, expected):
        assert azure_provider._normalize_state(power_state) == expected


# ── Parse Instance ID ──────────────────────────────────────────


class TestParseInstanceId:
    def test_valid(self, azure_provider):
        rg, name = azure_provider._parse_instance_id("my-rg/my-vm")
        assert rg == "my-rg"
        assert name == "my-vm"

    def test_invalid_no_slash(self, azure_provider):
        with pytest.raises(ValueError, match="Invalid Azure instance ID"):
            azure_provider._parse_instance_id("no-slash-here")

    def test_with_slash_in_name(self, azure_provider):
        """Only splits on first slash."""
        rg, name = azure_provider._parse_instance_id("rg/vm/extra")
        assert rg == "rg"
        assert name == "vm/extra"


# ── Extract Resource Group ─────────────────────────────────────


class TestExtractResourceGroup:
    def test_standard_id(self, azure_provider):
        vm_id = (
            "/subscriptions/sub-123/resourceGroups/my-rg"
            "/providers/Microsoft.Compute/virtualMachines/vm-1"
        )
        assert azure_provider._extract_resource_group(vm_id) == "my-rg"

    def test_invalid_id(self, azure_provider):
        with pytest.raises(ValueError, match="Could not extract"):
            azure_provider._extract_resource_group("/subscriptions/sub/nothing")
