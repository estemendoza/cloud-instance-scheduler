from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
from datetime import datetime


class InstanceState(str, Enum):
    """Normalized instance states across all providers."""
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


@dataclass
class InstanceInfo:
    """Normalized instance information from cloud providers."""
    id: str
    name: Optional[str]
    state: InstanceState
    tags: Dict[str, str]
    region: str
    provider: str  # 'aws', 'azure', 'gcp'
    instance_type: Optional[str] = None
    last_updated: Optional[datetime] = None


@dataclass
class ProviderCredentials:
    """Base credentials class."""
    pass


@dataclass
class AWSCredentials(ProviderCredentials):
    """AWS-specific credentials."""
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"  # Default region for STS calls
    session_token: Optional[str] = None


@dataclass
class AzureCredentials(ProviderCredentials):
    """Azure-specific credentials."""
    subscription_id: str
    tenant_id: str
    client_id: str
    client_secret: str


@dataclass
class GCPCredentials(ProviderCredentials):
    """GCP-specific credentials."""
    project_id: str
    service_account_json: str  # Service account JSON as string


@dataclass
class ProviderValidationResult:
    """Result of credential validation."""
    is_valid: bool
    error_message: Optional[str] = None
