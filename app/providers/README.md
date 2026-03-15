# Adding a New Cloud Provider

This guide walks you through adding a new cloud provider to the scheduler. The plugin system is designed so that **the frontend requires zero changes** — it dynamically fetches provider metadata from the backend.

You only need to touch **3 files**.

## Step 1: Define Credentials (`app/providers/models.py`)

Add a dataclass for your provider's credentials:

```python
@dataclass
class DigitalOceanCredentials(ProviderCredentials):
    """DigitalOcean-specific credentials."""
    api_token: str
```

Each field in the dataclass must match the `key` values you'll define in `CREDENTIAL_FIELDS` (Step 2).

## Step 2: Create the Provider (`app/providers/your_provider.py`)

Create a new file (e.g. `digitalocean.py`) with a class that extends `CloudProvider`. You need to set class-level metadata and implement 5 methods.

### Class Attributes (required)

| Attribute | Description | Example |
|---|---|---|
| `PROVIDER_TYPE` | Unique identifier (lowercase, no spaces) | `"digitalocean"` |
| `DISPLAY_NAME` | Human-readable name shown in the UI | `"DigitalOcean"` |
| `CREDENTIALS_CLASS` | The dataclass from Step 1 | `DigitalOceanCredentials` |
| `CREDENTIAL_FIELDS` | List of `CredentialFieldDef` describing the login form | See below |
| `REGIONS` | List of `RegionDef` for region/zone selection | See below |
| `COLOR` | Tailwind color name for UI badges | `"blue"` |
| `REGION_LABEL` | Label shown in the UI (`"Regions"` or `"Zones"`) | `"Regions"` |

Available colors: `orange`, `blue`, `red`, `green`, `purple`, `cyan`, `yellow`, `pink`, `slate`.

### Credential Fields

Each `CredentialFieldDef` describes one input in the credential form:

```python
CREDENTIAL_FIELDS = [
    CredentialFieldDef(
        key="api_token",        # Must match the credentials dataclass field name
        label="API Token",      # Shown as the input label
        field_type="password",  # "text", "password", or "textarea"
        secret=True,            # True = never sent back to the frontend
        required=True,          # Whether the field is required on create
    ),
]
```

- Fields with `secret=True` are encrypted and never returned in API responses.
- Fields with `secret=False` are returned as `credential_hints` so edit forms can pre-populate them.

### Regions

```python
REGIONS = [
    RegionDef("nyc1", "New York 1"),
    RegionDef("sfo3", "San Francisco 3"),
    RegionDef("ams3", "Amsterdam 3"),
]
```

### Abstract Methods

Implement these 5 methods:

```python
def validate_credentials(self) -> ProviderValidationResult:
    """Test that credentials work. Return ProviderValidationResult(is_valid=True) on success."""

def list_instances(self, regions: Optional[List[str]] = None) -> List[InstanceInfo]:
    """Return all compute instances, optionally filtered by region."""

def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
    """Return the current state of one instance (RUNNING, STOPPED, or UNKNOWN)."""

def start_instance(self, instance_id: str, region: str) -> bool:
    """Start a stopped instance. Return True on success."""

def stop_instance(self, instance_id: str, region: str) -> bool:
    """Stop a running instance. Return True on success."""
```

### Full Example

```python
import logging
from typing import List, Optional

from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    DigitalOceanCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult,
)

logger = logging.getLogger(__name__)


class DigitalOceanProvider(CloudProvider):
    PROVIDER_TYPE = "digitalocean"
    DISPLAY_NAME = "DigitalOcean"
    CREDENTIALS_CLASS = DigitalOceanCredentials
    COLOR = "blue"
    REGION_LABEL = "Regions"

    CREDENTIAL_FIELDS = [
        CredentialFieldDef(
            key="api_token", label="API Token",
            field_type="password", secret=True),
    ]

    REGIONS = [
        RegionDef("nyc1", "New York 1"),
        RegionDef("nyc3", "New York 3"),
        RegionDef("sfo3", "San Francisco 3"),
        RegionDef("ams3", "Amsterdam 3"),
        RegionDef("sgp1", "Singapore 1"),
        RegionDef("lon1", "London 1"),
        RegionDef("fra1", "Frankfurt 1"),
        RegionDef("blr1", "Bangalore 1"),
        RegionDef("syd1", "Sydney 1"),
    ]

    def __init__(self, credentials: DigitalOceanCredentials):
        super().__init__(credentials)
        self.credentials: DigitalOceanCredentials = credentials

    def validate_credentials(self) -> ProviderValidationResult:
        # Call the DigitalOcean API to verify the token
        ...

    def list_instances(self, regions: Optional[List[str]] = None) -> List[InstanceInfo]:
        # List all droplets, optionally filtering by region
        ...

    def get_instance_state(self, instance_id: str, region: str) -> InstanceState:
        # Get droplet status and map to InstanceState
        ...

    def start_instance(self, instance_id: str, region: str) -> bool:
        # Power on a droplet
        ...

    def stop_instance(self, instance_id: str, region: str) -> bool:
        # Power off (or shutdown) a droplet
        ...
```

## Step 3: Register the Provider (`app/providers/__init__.py`)

Import your class and add it to `_PROVIDER_CLASSES`:

```python
from app.providers.digitalocean import DigitalOceanProvider

_PROVIDER_CLASSES: List[Type[CloudProvider]] = [
    AWSEC2Provider,
    AzureVMProvider,
    GCPComputeProvider,
    DigitalOceanProvider,  # <-- add this line
]
```

That's it. Everything else is derived automatically:
- The provider registry, credential builder, and validation are all generated from this list.
- The frontend fetches provider metadata from `GET /api/v1/providers/metadata` and dynamically renders the provider selector, credential form, and region picker.

## How It Works Under the Hood

```
Provider class (aws_ec2.py)
    defines: PROVIDER_TYPE, CREDENTIAL_FIELDS, REGIONS, ...
        │
        ▼
__init__.py reads _PROVIDER_CLASSES
    builds: PROVIDER_REGISTRY, build_credentials(), get_non_secret_keys()
        │
        ▼
GET /api/v1/providers/metadata
    returns: all provider metadata as JSON
        │
        ▼
Frontend (Settings page)
    fetches metadata on load, renders forms dynamically
```

## Tips

- Look at `aws_ec2.py`, `azure_vm.py`, or `gcp_compute.py` for real-world examples.
- `instance_id` format is up to you. AWS uses `i-abc123`, Azure uses `resourceGroup/vmName`, GCP uses `zone/instance`. Pick whatever uniquely identifies an instance.
- `list_instances` should return `InstanceInfo` objects with `provider` set to your `PROVIDER_TYPE`.
- Handle errors gracefully in all methods — log them and return safe defaults (e.g. `InstanceState.UNKNOWN`) rather than letting exceptions propagate.
- If your provider uses zones instead of regions, set `REGION_LABEL = "Zones"` and populate `REGIONS` with zones.
