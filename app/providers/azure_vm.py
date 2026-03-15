import logging
from typing import List, Optional
from datetime import datetime, timezone

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import AzureError, ClientAuthenticationError

from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    AzureCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult
)

logger = logging.getLogger(__name__)


class AzureVMProvider(CloudProvider):
    """Azure VM provider implementation."""

    PROVIDER_TYPE = "azure"
    DISPLAY_NAME = "Azure"
    CREDENTIALS_CLASS = AzureCredentials
    COLOR = "blue"
    REGION_LABEL = "Regions"

    CREDENTIAL_FIELDS = [
        CredentialFieldDef(
            key="subscription_id", label="Subscription ID",
            field_type="text", secret=False),
        CredentialFieldDef(
            key="tenant_id", label="Tenant ID",
            field_type="text", secret=False),
        CredentialFieldDef(
            key="client_id", label="Client ID",
            field_type="text", secret=False),
        CredentialFieldDef(
            key="client_secret", label="Client Secret",
            field_type="password", secret=True),
    ]

    REGIONS = [
        RegionDef("eastus", "East US"),
        RegionDef("eastus2", "East US 2"),
        RegionDef("westus", "West US"),
        RegionDef("westus2", "West US 2"),
        RegionDef("westus3", "West US 3"),
        RegionDef("centralus", "Central US"),
        RegionDef("northcentralus", "North Central US"),
        RegionDef("southcentralus", "South Central US"),
        RegionDef("westcentralus", "West Central US"),
        RegionDef("canadacentral", "Canada Central"),
        RegionDef("canadaeast", "Canada East"),
        RegionDef("brazilsouth", "Brazil South"),
        RegionDef("northeurope", "North Europe"),
        RegionDef("westeurope", "West Europe"),
        RegionDef("uksouth", "UK South"),
        RegionDef("ukwest", "UK West"),
        RegionDef("francecentral", "France Central"),
        RegionDef("francesouth", "France South"),
        RegionDef("switzerlandnorth", "Switzerland North"),
        RegionDef("switzerlandwest", "Switzerland West"),
        RegionDef("germanywestcentral", "Germany West Central"),
        RegionDef("norwayeast", "Norway East"),
        RegionDef("norwaywest", "Norway West"),
        RegionDef("swedencentral", "Sweden Central"),
        RegionDef("polandcentral", "Poland Central"),
        RegionDef("qatarcentral", "Qatar Central"),
        RegionDef("uaenorth", "UAE North"),
        RegionDef("uaecentral", "UAE Central"),
        RegionDef("southafricanorth", "South Africa North"),
        RegionDef("southafricawest", "South Africa West"),
        RegionDef("eastasia", "East Asia"),
        RegionDef("southeastasia", "Southeast Asia"),
        RegionDef("australiaeast", "Australia East"),
        RegionDef("australiasoutheast", "Australia Southeast"),
        RegionDef("australiacentral", "Australia Central"),
        RegionDef("japaneast", "Japan East"),
        RegionDef("japanwest", "Japan West"),
        RegionDef("koreacentral", "Korea Central"),
        RegionDef("koreasouth", "Korea South"),
        RegionDef("centralindia", "Central India"),
        RegionDef("southindia", "South India"),
        RegionDef("westindia", "West India"),
    ]

    # Map Azure power states to normalized states
    STATE_MAPPING = {
        'poweredoff': InstanceState.STOPPED,
        'stopped': InstanceState.STOPPED,
        'deallocated': InstanceState.STOPPED,
        'deallocating': InstanceState.STOPPED,  # Transitioning to stopped
        'running': InstanceState.RUNNING,
        'starting': InstanceState.RUNNING,  # Transitioning to running
        'stopping': InstanceState.STOPPED,  # Transitioning to stopped
    }

    def __init__(self, credentials: AzureCredentials):
        """Initialize Azure VM provider."""
        super().__init__(credentials)
        if not isinstance(credentials, AzureCredentials):
            raise ValueError("Credentials must be AzureCredentials")
        self.credentials: AzureCredentials = credentials
        self._credential = None
        self._compute_client = None

    def _get_credential(self) -> ClientSecretCredential:
        """Get Azure credential object."""
        if self._credential is None:
            self._credential = ClientSecretCredential(
                tenant_id=self.credentials.tenant_id,
                client_id=self.credentials.client_id,
                client_secret=self.credentials.client_secret
            )
        return self._credential

    def _get_compute_client(self) -> ComputeManagementClient:
        """Get Azure Compute Management client."""
        if self._compute_client is None:
            self._compute_client = ComputeManagementClient(
                credential=self._get_credential(),
                subscription_id=self.credentials.subscription_id
            )
        return self._compute_client

    def _parse_instance_id(self, instance_id: str) -> tuple:
        """
        Parse composite instance ID into resource group and VM name.

        Instance ID format: resourceGroup/vmName
        """
        parts = instance_id.split('/', 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid Azure instance ID format:"
                f" {instance_id}."
                " Expected: resourceGroup/vmName")
        return parts[0], parts[1]

    def _make_instance_id(self, resource_group: str, vm_name: str) -> str:
        """Create composite instance ID from resource group and VM name."""
        return f"{resource_group}/{vm_name}"

    def _extract_resource_group(self, vm_id: str) -> str:
        """Extract resource group name from Azure resource ID."""
        # Azure resource ID format:
        # /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}
        parts = vm_id.split('/')
        for i, part in enumerate(parts):
            if part.lower() == 'resourcegroups' and i + 1 < len(parts):
                return parts[i + 1]
        raise ValueError(f"Could not extract resource group from: {vm_id}")

    def _normalize_state(self, power_state: Optional[str]) -> InstanceState:
        """
        Normalize Azure power state to InstanceState enum.

        Azure power states come as "PowerState/running", "PowerState/deallocated", etc.
        """
        if not power_state:
            return InstanceState.UNKNOWN

        # Extract state from "PowerState/xxx" format
        if '/' in power_state:
            state = power_state.split('/')[-1].lower()
        else:
            state = power_state.lower()

        return self.STATE_MAPPING.get(state, InstanceState.UNKNOWN)

    def _get_power_state(self, resource_group: str, vm_name: str) -> Optional[str]:
        """Get power state from instance view."""
        try:
            compute = self._get_compute_client()
            instance_view = compute.virtual_machines.instance_view(
                resource_group_name=resource_group,
                vm_name=vm_name
            )

            for status in instance_view.statuses or []:
                if status.code and status.code.startswith('PowerState/'):
                    return status.code

            return None
        except AzureError:
            return None

    def validate_credentials(self) -> ProviderValidationResult:
        """Validate Azure credentials by attempting to list VMs."""
        try:
            compute = self._get_compute_client()
            # Try to list VMs - this validates credentials
            # We just need to start the iteration, not consume all results
            list(compute.virtual_machines.list_all())
            return ProviderValidationResult(is_valid=True)
        except ClientAuthenticationError as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"Azure authentication failed: {str(e)}"
            )
        except AzureError as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"Azure credential validation failed: {str(e)}"
            )
        except Exception as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"Azure credential validation error: {str(e)}"
            )

    def list_instances(self, regions: Optional[List[str]] = None) -> List[InstanceInfo]:
        """List all VMs in the subscription, optionally filtered by regions."""
        instances = []

        try:
            compute = self._get_compute_client()

            for vm in compute.virtual_machines.list_all():
                # Filter by region if specified
                if regions and vm.location not in regions:
                    continue

                try:
                    # Extract resource group from VM ID
                    resource_group = self._extract_resource_group(vm.id)

                    # Get power state from instance view
                    power_state = self._get_power_state(resource_group, vm.name)

                    # Extract tags
                    tags = dict(vm.tags) if vm.tags else {}

                    # Get instance name (prefer Name tag, fall back to VM name)
                    name = tags.get('Name', vm.name)

                    instances.append(
                                     InstanceInfo(
                                         id=self._make_instance_id(
                                             resource_group, vm.name),
                                         name=name, state=self._normalize_state(
                                             power_state),
                                         tags=tags, region=vm.location,
                                         provider='azure',
                                         instance_type=vm.hardware_profile.vm_size
                                         if vm.hardware_profile else None,
                                         last_updated=datetime.now(timezone.utc)))
                except Exception as e:
                    logger.error(f"Error processing VM {vm.name}: {e}")
                    continue

        except AzureError as e:
            logger.error(f"Error listing Azure VMs: {e}")
        except Exception as e:
            logger.error(f"Unexpected error listing Azure VMs: {e}")

        return instances

    def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
        """Get the current state of a specific Azure VM."""
        try:
            resource_group, vm_name = self._parse_instance_id(instance_id)
            power_state = self._get_power_state(resource_group, vm_name)
            return self._normalize_state(power_state)
        except ValueError as e:
            logger.error(f"Invalid instance ID: {e}")
            return InstanceState.UNKNOWN
        except AzureError as e:
            logger.error(f"Error getting VM state for {instance_id}: {e}")
            return InstanceState.UNKNOWN
        except Exception as e:
            logger.error(f"Unexpected error getting VM state for {instance_id}: {e}")
            return InstanceState.UNKNOWN

    def start_instance(self, instance_id: str, region: str) -> bool:
        """Start a stopped Azure VM."""
        try:
            resource_group, vm_name = self._parse_instance_id(instance_id)
            compute = self._get_compute_client()

            # begin_start returns a poller - we wait for completion
            poller = compute.virtual_machines.begin_start(
                resource_group_name=resource_group,
                vm_name=vm_name
            )
            poller.result()  # Wait for operation to complete
            return True
        except AzureError as e:
            # Check if VM is already running
            if 'already running' in str(e).lower():
                return True
            raise

    def stop_instance(self, instance_id: str, region: str) -> bool:
        """
        Stop a running Azure VM using deallocate.

        Note: We use deallocate instead of power_off because:
        - deallocate releases compute resources and stops billing
        - power_off keeps resources allocated and continues billing
        """
        try:
            resource_group, vm_name = self._parse_instance_id(instance_id)
            compute = self._get_compute_client()

            # begin_deallocate releases resources and stops billing
            poller = compute.virtual_machines.begin_deallocate(
                resource_group_name=resource_group,
                vm_name=vm_name
            )
            poller.result()  # Wait for operation to complete
            return True
        except AzureError as e:
            # Check if VM is already stopped/deallocated
            if 'already deallocated' in str(e).lower():
                return True
            raise
