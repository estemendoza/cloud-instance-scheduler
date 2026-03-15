import json
import logging
from typing import List, Optional
from datetime import datetime, timezone

from google.cloud import compute_v1
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError, Forbidden, NotFound

from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    GCPCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult
)

logger = logging.getLogger(__name__)


class GCPComputeProvider(CloudProvider):
    """GCP Compute Engine provider implementation."""

    PROVIDER_TYPE = "gcp"
    DISPLAY_NAME = "GCP"
    CREDENTIALS_CLASS = GCPCredentials
    COLOR = "red"
    REGION_LABEL = "Zones"

    CREDENTIAL_FIELDS = [
        CredentialFieldDef(
            key="project_id", label="Project ID",
            field_type="text", secret=False),
        CredentialFieldDef(
            key="service_account_json", label="Service Account JSON",
            field_type="textarea", secret=True),
    ]

    REGIONS = [
        # US
        RegionDef("us-central1-a", "Iowa (a)"),
        RegionDef("us-central1-b", "Iowa (b)"),
        RegionDef("us-central1-c", "Iowa (c)"),
        RegionDef("us-central1-f", "Iowa (f)"),
        RegionDef("us-east1-b", "South Carolina (b)"),
        RegionDef("us-east1-c", "South Carolina (c)"),
        RegionDef("us-east1-d", "South Carolina (d)"),
        RegionDef("us-east4-a", "N. Virginia (a)"),
        RegionDef("us-east4-b", "N. Virginia (b)"),
        RegionDef("us-east4-c", "N. Virginia (c)"),
        RegionDef("us-east5-a", "Columbus (a)"),
        RegionDef("us-east5-b", "Columbus (b)"),
        RegionDef("us-east5-c", "Columbus (c)"),
        RegionDef("us-west1-a", "Oregon (a)"),
        RegionDef("us-west1-b", "Oregon (b)"),
        RegionDef("us-west1-c", "Oregon (c)"),
        RegionDef("us-west2-a", "Los Angeles (a)"),
        RegionDef("us-west2-b", "Los Angeles (b)"),
        RegionDef("us-west2-c", "Los Angeles (c)"),
        RegionDef("us-west3-a", "Salt Lake City (a)"),
        RegionDef("us-west3-b", "Salt Lake City (b)"),
        RegionDef("us-west3-c", "Salt Lake City (c)"),
        RegionDef("us-west4-a", "Las Vegas (a)"),
        RegionDef("us-west4-b", "Las Vegas (b)"),
        RegionDef("us-west4-c", "Las Vegas (c)"),
        RegionDef("us-south1-a", "Dallas (a)"),
        RegionDef("us-south1-b", "Dallas (b)"),
        RegionDef("us-south1-c", "Dallas (c)"),
        # Europe
        RegionDef("europe-west1-b", "Belgium (b)"),
        RegionDef("europe-west1-c", "Belgium (c)"),
        RegionDef("europe-west1-d", "Belgium (d)"),
        RegionDef("europe-west2-a", "London (a)"),
        RegionDef("europe-west2-b", "London (b)"),
        RegionDef("europe-west2-c", "London (c)"),
        RegionDef("europe-west3-a", "Frankfurt (a)"),
        RegionDef("europe-west3-b", "Frankfurt (b)"),
        RegionDef("europe-west3-c", "Frankfurt (c)"),
        RegionDef("europe-west4-a", "Netherlands (a)"),
        RegionDef("europe-west4-b", "Netherlands (b)"),
        RegionDef("europe-west4-c", "Netherlands (c)"),
        RegionDef("europe-north1-a", "Finland (a)"),
        RegionDef("europe-north1-b", "Finland (b)"),
        RegionDef("europe-north1-c", "Finland (c)"),
        # Asia Pacific
        RegionDef("asia-east1-a", "Taiwan (a)"),
        RegionDef("asia-east1-b", "Taiwan (b)"),
        RegionDef("asia-east1-c", "Taiwan (c)"),
        RegionDef("asia-east2-a", "Hong Kong (a)"),
        RegionDef("asia-east2-b", "Hong Kong (b)"),
        RegionDef("asia-east2-c", "Hong Kong (c)"),
        RegionDef("asia-northeast1-a", "Tokyo (a)"),
        RegionDef("asia-northeast1-b", "Tokyo (b)"),
        RegionDef("asia-northeast1-c", "Tokyo (c)"),
        RegionDef("asia-northeast2-a", "Osaka (a)"),
        RegionDef("asia-northeast2-b", "Osaka (b)"),
        RegionDef("asia-northeast2-c", "Osaka (c)"),
        RegionDef("asia-southeast1-a", "Singapore (a)"),
        RegionDef("asia-southeast1-b", "Singapore (b)"),
        RegionDef("asia-southeast1-c", "Singapore (c)"),
        RegionDef("asia-southeast2-a", "Jakarta (a)"),
        RegionDef("asia-southeast2-b", "Jakarta (b)"),
        RegionDef("asia-southeast2-c", "Jakarta (c)"),
        RegionDef("asia-south1-a", "Mumbai (a)"),
        RegionDef("asia-south1-b", "Mumbai (b)"),
        RegionDef("asia-south1-c", "Mumbai (c)"),
        # Other
        RegionDef("australia-southeast1-a", "Sydney (a)"),
        RegionDef("australia-southeast1-b", "Sydney (b)"),
        RegionDef("australia-southeast1-c", "Sydney (c)"),
        RegionDef("southamerica-east1-a", "São Paulo (a)"),
        RegionDef("southamerica-east1-b", "São Paulo (b)"),
        RegionDef("southamerica-east1-c", "São Paulo (c)"),
        RegionDef("me-west1-a", "Tel Aviv (a)"),
        RegionDef("me-west1-b", "Tel Aviv (b)"),
        RegionDef("me-west1-c", "Tel Aviv (c)"),
    ]

    # Map GCP instance statuses to normalized states
    STATE_MAPPING = {
        'RUNNING': InstanceState.RUNNING,
        'PROVISIONING': InstanceState.RUNNING,
        'STAGING': InstanceState.RUNNING,
        'STOPPED': InstanceState.STOPPED,
        'TERMINATED': InstanceState.STOPPED,
        'SUSPENDED': InstanceState.STOPPED,
        'STOPPING': InstanceState.STOPPED,
        'SUSPENDING': InstanceState.STOPPED,
    }

    def __init__(self, credentials: GCPCredentials):
        """Initialize GCP Compute Engine provider."""
        super().__init__(credentials)
        if not isinstance(credentials, GCPCredentials):
            raise ValueError("Credentials must be GCPCredentials")
        self.credentials: GCPCredentials = credentials
        self._gcp_credentials = None
        self._instances_client = None

    def _get_gcp_credentials(self) -> service_account.Credentials:
        """Get GCP credential object from service account JSON."""
        if self._gcp_credentials is None:
            service_account_info = json.loads(self.credentials.service_account_json)
            self._gcp_credentials = (
                service_account.Credentials
                .from_service_account_info(
                    service_account_info,
                    scopes=[
                        'https://www.googleapis.com'
                        '/auth/compute'
                    ],
                )
            )
        return self._gcp_credentials

    def _get_instances_client(self) -> compute_v1.InstancesClient:
        """Get GCP Compute Engine instances client."""
        if self._instances_client is None:
            self._instances_client = compute_v1.InstancesClient(
                credentials=self._get_gcp_credentials()
            )
        return self._instances_client

    def _extract_zone_from_url(self, zone_url: str) -> str:
        """Extract zone name from a full zone URL.

        Example: '.../projects/my-project/zones/us-east1-b'
        Returns: 'us-east1-b'
        """
        return zone_url.rsplit('/', 1)[-1]

    def _normalize_state(self, gcp_status: Optional[str]) -> InstanceState:
        """Normalize GCP instance status to InstanceState enum."""
        if not gcp_status:
            return InstanceState.UNKNOWN
        return self.STATE_MAPPING.get(gcp_status.upper(), InstanceState.UNKNOWN)

    def validate_credentials(self) -> ProviderValidationResult:
        """Validate GCP credentials by attempting to list instances."""
        try:
            client = self._get_instances_client()
            request = compute_v1.AggregatedListInstancesRequest(
                project=self.credentials.project_id,
                max_results=1
            )
            # Consume just the first result to verify credentials
            list(client.aggregated_list(request=request))
            return ProviderValidationResult(is_valid=True)
        except json.JSONDecodeError:
            return ProviderValidationResult(
                is_valid=False,
                error_message="Invalid service account JSON format"
            )
        except Forbidden as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=(
                    "GCP authentication failed:"
                    f" insufficient permissions - {str(e)}"
                )
            )
        except GoogleAPIError as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"GCP credential validation failed: {str(e)}"
            )
        except Exception as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"GCP credential validation error: {str(e)}"
            )

    def list_instances(self, regions: Optional[List[str]] = None) -> List[InstanceInfo]:
        """List all Compute Engine instances, optionally filtered by zones.

        Note: The `regions` parameter here actually filters by GCP zones
        (e.g., 'us-east1-b') since GCP instances live in zones.
        """
        instances = []

        try:
            client = self._get_instances_client()
            request = compute_v1.AggregatedListInstancesRequest(
                project=self.credentials.project_id
            )

            for zone_key, response in client.aggregated_list(request=request):
                if not response.instances:
                    continue

                # zone_key format: "zones/us-east1-b"
                zone = zone_key.split('/')[-1] if '/' in zone_key else zone_key

                # Filter by zones if specified
                if regions and zone not in regions:
                    continue

                for instance in response.instances:
                    try:
                        # Extract labels (GCP equivalent of tags)
                        labels = dict(instance.labels) if instance.labels else {}

                        # Get instance name
                        name = labels.get('name', instance.name)

                        instances.append(
                            InstanceInfo(
                                id=instance.name, name=name,
                                state=self._normalize_state(instance.status),
                                tags=labels, region=zone, provider='gcp',
                                instance_type=self._extract_machine_type(
                                    instance.machine_type),
                                last_updated=datetime.now(timezone.utc)))
                    except Exception as e:
                        logger.error(
                            f"Error processing GCP instance {instance.name}: {e}")
                        continue

        except GoogleAPIError as e:
            logger.error(f"Error listing GCP instances: {e}")
        except Exception as e:
            logger.error(f"Unexpected error listing GCP instances: {e}")

        return instances

    def _extract_machine_type(self, machine_type_url: Optional[str]) -> Optional[str]:
        """Extract machine type name from full URL.

        Example: '.../machineTypes/e2-medium' -> 'e2-medium'
        """
        if not machine_type_url:
            return None
        return machine_type_url.rsplit('/', 1)[-1]

    def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
        """Get the current state of a specific GCP instance.

        Args:
            instance_id: The instance name
            region: The zone where the instance is located
        """
        try:
            client = self._get_instances_client()
            instance = client.get(
                project=self.credentials.project_id,
                zone=region,
                instance=instance_id
            )
            return self._normalize_state(instance.status)
        except NotFound:
            return InstanceState.UNKNOWN
        except GoogleAPIError as e:
            logger.error(f"Error getting GCP instance state for {instance_id}: {e}")
            return InstanceState.UNKNOWN
        except Exception as e:
            logger.error(
                f"Unexpected error getting GCP instance state for {instance_id}: {e}")
            return InstanceState.UNKNOWN

    def start_instance(self, instance_id: str, region: str) -> bool:
        """Start a stopped GCP instance.

        Args:
            instance_id: The instance name
            region: The zone where the instance is located
        """
        try:
            client = self._get_instances_client()
            operation = client.start(
                project=self.credentials.project_id,
                zone=region,
                instance=instance_id
            )
            operation.result()  # Wait for operation to complete
            return True
        except GoogleAPIError as e:
            if 'already' in str(e).lower():
                return True
            raise

    def stop_instance(self, instance_id: str, region: str) -> bool:
        """Stop a running GCP instance.

        Args:
            instance_id: The instance name
            region: The zone where the instance is located
        """
        try:
            client = self._get_instances_client()
            operation = client.stop(
                project=self.credentials.project_id,
                zone=region,
                instance=instance_id
            )
            operation.result()  # Wait for operation to complete
            return True
        except GoogleAPIError as e:
            if 'already' in str(e).lower():
                return True
            raise
