from typing import Dict, List, Set, Type

from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    ProviderCredentials,
    AWSCredentials,
    AzureCredentials,
    GCPCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult
)
from app.providers.aws_ec2 import AWSEC2Provider
from app.providers.azure_vm import AzureVMProvider
from app.providers.gcp_compute import GCPComputeProvider

# -----------------------------------------------------------
# Provider registry: add new providers here (one line each).
# -----------------------------------------------------------
_PROVIDER_CLASSES: List[Type[CloudProvider]] = [
    AWSEC2Provider,
    AzureVMProvider,
    GCPComputeProvider,
]

# Derived lookups — no manual maintenance needed.
PROVIDER_REGISTRY: Dict[str, Type[CloudProvider]] = {
    cls.PROVIDER_TYPE: cls for cls in _PROVIDER_CLASSES
}


def get_valid_provider_types() -> List[str]:
    """Return list of registered provider type strings."""
    return list(PROVIDER_REGISTRY.keys())


def build_credentials(
    provider_type: str, creds_dict: Dict,
) -> ProviderCredentials:
    """Convert a plain credentials dict into the typed dataclass."""
    provider_class = PROVIDER_REGISTRY.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unsupported provider type: {provider_type}")
    return provider_class.CREDENTIALS_CLASS(**creds_dict)


def get_non_secret_keys(provider_type: str) -> Set[str]:
    """Get non-secret credential keys for a provider."""
    provider_class = PROVIDER_REGISTRY.get(provider_type.lower())
    if not provider_class:
        return set()
    return provider_class.get_non_secret_keys()


def get_all_provider_metadata() -> List[dict]:
    """Return metadata for all registered providers."""
    return [cls.get_metadata() for cls in _PROVIDER_CLASSES]


def get_provider(
    provider_type: str, credentials: ProviderCredentials,
) -> CloudProvider:
    """
    Factory function to get a provider instance.

    Args:
        provider_type: Type of provider (e.g. 'aws', 'azure', 'gcp')
        credentials: Provider-specific credentials

    Returns:
        CloudProvider instance

    Raises:
        ValueError: If provider_type is not supported
    """
    provider_class = PROVIDER_REGISTRY.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unsupported provider type: {provider_type}")
    return provider_class(credentials)


__all__ = [
    'CloudProvider',
    'CredentialFieldDef',
    'RegionDef',
    'InstanceInfo',
    'InstanceState',
    'ProviderCredentials',
    'AWSCredentials',
    'AzureCredentials',
    'GCPCredentials',
    'ProviderValidationResult',
    'AWSEC2Provider',
    'AzureVMProvider',
    'GCPComputeProvider',
    'PROVIDER_REGISTRY',
    'get_provider',
    'build_credentials',
    'get_valid_provider_types',
    'get_non_secret_keys',
    'get_all_provider_metadata',
]
