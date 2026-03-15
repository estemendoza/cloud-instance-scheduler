from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Type

from app.providers.models import (
    InstanceInfo,
    InstanceState,
    ProviderCredentials,
    ProviderValidationResult
)


@dataclass
class CredentialFieldDef:
    """Defines a single credential field for a provider."""
    key: str
    label: str
    field_type: str = "text"    # "text", "password", "textarea"
    required: bool = True
    secret: bool = False        # If True, never returned to frontend
    placeholder: str = ""


@dataclass
class RegionDef:
    """Defines a selectable region or zone."""
    code: str
    name: str


class CloudProvider(ABC):
    """
    Abstract base class for cloud provider implementations.

    IMPORTANT: Provider implementations MUST be stateless and MUST NOT
    access the database directly. All credentials are passed per-call.

    To add a new provider, subclass this and set all class attributes
    (PROVIDER_TYPE, DISPLAY_NAME, etc.), then implement the abstract
    methods below. See existing providers for examples.
    """

    # --- Metadata: subclasses MUST override these ---
    PROVIDER_TYPE: str = ""
    DISPLAY_NAME: str = ""
    CREDENTIALS_CLASS: Type[ProviderCredentials] = ProviderCredentials
    CREDENTIAL_FIELDS: List[CredentialFieldDef] = []
    REGIONS: List[RegionDef] = []

    # --- Optional metadata ---
    REGION_LABEL: str = "Regions"   # "Regions" or "Zones"
    COLOR: str = "slate"            # Tailwind color for UI badges

    def __init__(self, credentials: ProviderCredentials):
        """
        Initialize provider with credentials.

        Args:
            credentials: Provider-specific credentials
        """
        self.credentials = credentials

    @classmethod
    def get_non_secret_keys(cls) -> set:
        """Derive non-secret credential keys from CREDENTIAL_FIELDS."""
        return {f.key for f in cls.CREDENTIAL_FIELDS if not f.secret}

    @classmethod
    def get_metadata(cls) -> dict:
        """Return provider metadata as a serializable dict."""
        return {
            "provider_type": cls.PROVIDER_TYPE,
            "display_name": cls.DISPLAY_NAME,
            "color": cls.COLOR,
            "region_label": cls.REGION_LABEL,
            "credential_fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "type": f.field_type,
                    "required": f.required,
                    "secret": f.secret,
                    "placeholder": f.placeholder,
                }
                for f in cls.CREDENTIAL_FIELDS
            ],
            "regions": [
                {"code": r.code, "name": r.name}
                for r in cls.REGIONS
            ],
        }

    @abstractmethod
    def validate_credentials(self) -> ProviderValidationResult:
        """
        Validate that the provided credentials are valid.

        Returns:
            ProviderValidationResult with success/failure and error message
        """
        pass

    @abstractmethod
    def list_instances(
        self, regions: Optional[List[str]] = None,
    ) -> List[InstanceInfo]:
        """
        List all compute instances accessible with the provided credentials.

        Args:
            regions: Optional list of regions to scan.
                If None/empty, list from all regions.

        Returns:
            List of InstanceInfo objects
        """
        pass

    @abstractmethod
    def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
        """
        Get the current state of a specific instance.

        Args:
            instance_id: Cloud provider's instance identifier
            region: Region where the instance is located

        Returns:
            Normalized InstanceState
        """
        pass

    @abstractmethod
    def start_instance(self, instance_id: str, region: str) -> bool:
        """
        Start a stopped instance.

        Args:
            instance_id: Cloud provider's instance identifier
            region: Region where the instance is located

        Returns:
            True if successful or already running, False on error
        """
        pass

    @abstractmethod
    def stop_instance(self, instance_id: str, region: str) -> bool:
        """
        Stop a running instance.

        Args:
            instance_id: Cloud provider's instance identifier
            region: Region where the instance is located

        Returns:
            True if successful or already stopped, False on error
        """
        pass
