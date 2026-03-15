import logging

import boto3
from botocore.exceptions import ClientError
from typing import List, Optional
from datetime import datetime, timezone

from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    AWSCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult
)

logger = logging.getLogger(__name__)


class AWSEC2Provider(CloudProvider):
    """AWS EC2 provider implementation."""

    PROVIDER_TYPE = "aws"
    DISPLAY_NAME = "AWS"
    CREDENTIALS_CLASS = AWSCredentials
    COLOR = "orange"
    REGION_LABEL = "Regions"

    CREDENTIAL_FIELDS = [
        CredentialFieldDef(
            key="access_key_id", label="Access Key ID",
            field_type="text", secret=False),
        CredentialFieldDef(
            key="secret_access_key", label="Secret Access Key",
            field_type="password", secret=True),
    ]

    REGIONS = [
        RegionDef("us-east-1", "US East (N. Virginia)"),
        RegionDef("us-east-2", "US East (Ohio)"),
        RegionDef("us-west-1", "US West (N. California)"),
        RegionDef("us-west-2", "US West (Oregon)"),
        RegionDef("af-south-1", "Africa (Cape Town)"),
        RegionDef("ap-east-1", "Asia Pacific (Hong Kong)"),
        RegionDef("ap-east-2", "Asia Pacific (Taipei)"),
        RegionDef("ap-south-1", "Asia Pacific (Mumbai)"),
        RegionDef("ap-south-2", "Asia Pacific (Hyderabad)"),
        RegionDef("ap-southeast-1", "Asia Pacific (Singapore)"),
        RegionDef("ap-southeast-2", "Asia Pacific (Sydney)"),
        RegionDef("ap-southeast-3", "Asia Pacific (Jakarta)"),
        RegionDef("ap-southeast-4", "Asia Pacific (Melbourne)"),
        RegionDef("ap-southeast-5", "Asia Pacific (Malaysia)"),
        RegionDef("ap-southeast-6", "Asia Pacific (New Zealand)"),
        RegionDef("ap-southeast-7", "Asia Pacific (Thailand)"),
        RegionDef("ap-northeast-1", "Asia Pacific (Tokyo)"),
        RegionDef("ap-northeast-2", "Asia Pacific (Seoul)"),
        RegionDef("ap-northeast-3", "Asia Pacific (Osaka)"),
        RegionDef("ca-central-1", "Canada (Central)"),
        RegionDef("ca-west-1", "Canada West (Calgary)"),
        RegionDef("eu-central-1", "Europe (Frankfurt)"),
        RegionDef("eu-central-2", "Europe (Zurich)"),
        RegionDef("eu-west-1", "Europe (Ireland)"),
        RegionDef("eu-west-2", "Europe (London)"),
        RegionDef("eu-west-3", "Europe (Paris)"),
        RegionDef("eu-south-1", "Europe (Milan)"),
        RegionDef("eu-south-2", "Europe (Spain)"),
        RegionDef("eu-north-1", "Europe (Stockholm)"),
        RegionDef("il-central-1", "Israel (Tel Aviv)"),
        RegionDef("me-south-1", "Middle East (Bahrain)"),
        RegionDef("me-central-1", "Middle East (UAE)"),
        RegionDef("mx-central-1", "Mexico (Central)"),
        RegionDef("sa-east-1", "South America (São Paulo)"),
    ]

    # Map EC2 states to normalized states
    STATE_MAPPING = {
        'running': InstanceState.RUNNING,
        'stopped': InstanceState.STOPPED,
        'pending': InstanceState.RUNNING,  # Transitioning to running
        'stopping': InstanceState.STOPPED,  # Transitioning to stopped
        'shutting-down': InstanceState.STOPPED,
        'terminated': InstanceState.UNKNOWN,
        # Any other state
    }

    def __init__(self, credentials: AWSCredentials):
        """Initialize AWS EC2 provider."""
        super().__init__(credentials)
        if not isinstance(credentials, AWSCredentials):
            raise ValueError("Credentials must be AWSCredentials")
        self.credentials: AWSCredentials = credentials

    def _get_session_kwargs(self, region: Optional[str] = None) -> dict:
        """Get common session kwargs for boto3 clients."""
        kwargs = {
            'aws_access_key_id': self.credentials.access_key_id,
            'aws_secret_access_key': self.credentials.secret_access_key,
            'region_name': region or self.credentials.region
        }
        if self.credentials.session_token:
            kwargs['aws_session_token'] = self.credentials.session_token
        return kwargs

    def _get_ec2_client(self, region: Optional[str] = None):
        """Create an EC2 client for the specified region."""
        return boto3.client('ec2', **self._get_session_kwargs(region))

    def _get_sts_client(self, region: Optional[str] = None):
        """Create an STS client for credential validation."""
        return boto3.client('sts', **self._get_session_kwargs(region))

    def _normalize_state(self, ec2_state: str) -> InstanceState:
        """Normalize EC2 state to InstanceState enum."""
        return self.STATE_MAPPING.get(ec2_state.lower(), InstanceState.UNKNOWN)

    def validate_credentials(self) -> ProviderValidationResult:
        """Validate AWS credentials using STS GetCallerIdentity.

        This is the most reliable way to validate credentials as it:
        - Works with any valid AWS credentials
        - Doesn't require specific IAM permissions
        - Is specifically designed to verify identity
        """
        try:
            sts = self._get_sts_client()
            # GetCallerIdentity works with any valid credentials
            sts.get_caller_identity()
            return ProviderValidationResult(is_valid=True)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            return ProviderValidationResult(
                is_valid=False,
                error_message=(
                    f"AWS credential validation failed:"
                    f" {error_code} - {str(e)}"
                )
            )
        except Exception as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"AWS credential validation error: {str(e)}"
            )

    def list_instances(self, regions: Optional[List[str]] = None) -> List[InstanceInfo]:
        """List all EC2 instances in the specified regions or all regions."""
        instances = []

        try:
            if regions:
                target_regions = regions
            else:
                # List all regions
                ec2 = self._get_ec2_client()
                response = ec2.describe_regions()
                target_regions = [r['RegionName'] for r in response['Regions']]

            for region_name in target_regions:
                try:
                    ec2 = self._get_ec2_client(region_name)
                    paginator = ec2.get_paginator('describe_instances')

                    for page in paginator.paginate():
                        for reservation in page['Reservations']:
                            for instance in reservation['Instances']:
                                # Extract tags
                                tags = {
                                    tag['Key']: tag['Value']
                                    for tag in instance.get('Tags', [])}

                                # Get instance name from tags
                                name = tags.get('Name')

                                instances.append(InstanceInfo(
                                    id=instance['InstanceId'],
                                    name=name,
                                    state=self._normalize_state(
                                        instance['State']['Name']
                                    ),
                                    tags=tags,
                                    region=region_name,
                                    provider='aws',
                                    instance_type=instance.get(
                                        'InstanceType'
                                    ),
                                    last_updated=datetime.now(
                                        timezone.utc
                                    ),
                                ))
                except ClientError as e:
                    # Log error but continue with other regions
                    logger.error(
                        "Error listing instances in region %s: %s",
                        region_name, e,
                    )
                    continue

        except Exception as e:
            logger.error("Error listing EC2 instances: %s", e)

        return instances

    def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
        """Get the current state of a specific EC2 instance."""
        try:
            ec2 = self._get_ec2_client(region)
            response = ec2.describe_instances(InstanceIds=[instance_id])

            if response['Reservations']:
                instance = response['Reservations'][0]['Instances'][0]
                return self._normalize_state(instance['State']['Name'])

            return InstanceState.UNKNOWN
        except ClientError:
            return InstanceState.UNKNOWN
        except Exception:
            return InstanceState.UNKNOWN

    def start_instance(self, instance_id: str, region: str) -> bool:
        """Start a stopped EC2 instance."""
        try:
            ec2 = self._get_ec2_client(region)
            ec2.start_instances(InstanceIds=[instance_id])
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            # If instance is already running, consider it success
            if 'IncorrectInstanceState' in error_code:
                return True
            raise

    def stop_instance(self, instance_id: str, region: str) -> bool:
        """Stop a running EC2 instance."""
        try:
            ec2 = self._get_ec2_client(region)
            ec2.stop_instances(InstanceIds=[instance_id])
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            # If instance is already stopped, consider it success
            if 'IncorrectInstanceState' in error_code:
                return True
            raise
