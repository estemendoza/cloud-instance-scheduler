---
sidebar_position: 10
---

# Contributing a Provider

CIS uses a plugin-like provider architecture. To add support for a new cloud provider, you implement a single Python class, register it, and you're done — the frontend automatically generates credential forms, region pickers, and provider badges from your class metadata. No frontend changes needed.

This guide walks through the process using a fictional **DigitalOcean** provider as an example.

## Architecture overview

Here's how the pieces fit together:

```
CloudProvider subclass  →  provider registry  →  /api/v1/providers/metadata  →  frontend
  (your code)              (__init__.py)           (auto-generated)              (auto-rendered)
```

Key files you'll work with:

| File | Purpose |
|------|---------|
| `app/providers/base.py` | Abstract base class and helper dataclasses |
| `app/providers/models.py` | Shared models: `InstanceInfo`, `InstanceState`, `ProviderCredentials` |
| `app/providers/__init__.py` | Provider registry — where you register your new provider |

## Step 1: Define your credentials

Add a credentials dataclass to `app/providers/models.py`. Each provider has its own credentials shape — CIS encrypts these at rest and never exposes secret fields to the frontend.

```python
@dataclass
class DigitalOceanCredentials(ProviderCredentials):
    """DigitalOcean API credentials."""
    api_token: str
```

Keep it simple — only include what's needed to authenticate API calls.

## Step 2: Create the provider module

Create `app/providers/digitalocean.py` and subclass `CloudProvider`. You need to set class-level metadata and implement five abstract methods.

### Class metadata

```python
from app.providers.base import CloudProvider, CredentialFieldDef, RegionDef
from app.providers.models import (
    DigitalOceanCredentials,
    InstanceInfo,
    InstanceState,
    ProviderValidationResult,
)


class DigitalOceanProvider(CloudProvider):
    PROVIDER_TYPE = "digitalocean"
    DISPLAY_NAME = "DigitalOcean"
    CREDENTIALS_CLASS = DigitalOceanCredentials
    COLOR = "blue"                   # Tailwind color for UI badges
    REGION_LABEL = "Regions"         # or "Zones" for providers like GCP

    CREDENTIAL_FIELDS = [
        CredentialFieldDef(
            key="api_token",
            label="API Token",
            field_type="password",   # "text", "password", or "textarea"
            required=True,
            secret=True,             # never returned to the frontend
            placeholder="dop_v1_...",
        ),
    ]

    REGIONS = [
        RegionDef(code="nyc1", name="New York 1"),
        RegionDef(code="sfo3", name="San Francisco 3"),
        RegionDef(code="ams3", name="Amsterdam 3"),
        # ... add all supported regions
    ]
```

The `CREDENTIAL_FIELDS` list drives the frontend form. Each field becomes an input — `field_type` controls whether it renders as a text input, password field, or textarea (useful for JSON keys). Fields marked `secret=True` are never sent back to the browser.

The `REGIONS` list populates the region picker in the UI.

### Abstract methods

Implement these five methods:

| Method | Purpose | Returns |
|--------|---------|---------|
| `validate_credentials()` | Check credentials are valid | `ProviderValidationResult` |
| `list_instances(regions)` | Discover all compute instances | `List[InstanceInfo]` |
| `get_instance_state(id, region)` | Get current state of one instance | `InstanceState` |
| `start_instance(id, region)` | Start a stopped instance | `bool` |
| `stop_instance(id, region)` | Stop a running instance | `bool` |

**Important rules:**

- Providers must be **stateless** — don't store anything between calls
- Providers must **not access the database** — all data is passed in via the constructor
- Handle **idempotent operations** — starting an already-running instance should return `True`, not raise an error

### Implementation

```python
    def validate_credentials(self) -> ProviderValidationResult:
        """Make a lightweight API call to verify the token works."""
        try:
            # e.g., call GET /v2/account
            client = self._get_client()
            client.get_account()
            return ProviderValidationResult(is_valid=True)
        except AuthError as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=f"Authentication failed: {e}",
            )
        except Exception as e:
            return ProviderValidationResult(
                is_valid=False,
                error_message=str(e),
            )

    def list_instances(
        self, regions: Optional[List[str]] = None,
    ) -> List[InstanceInfo]:
        """List all droplets, optionally filtered by region."""
        client = self._get_client()
        droplets = client.list_droplets()

        results = []
        for droplet in droplets:
            # Skip if region filter is active and doesn't match
            if regions and droplet.region not in regions:
                continue

            results.append(InstanceInfo(
                id=str(droplet.id),
                name=droplet.name,
                state=self._map_state(droplet.status),
                tags={t: "" for t in droplet.tags},
                region=droplet.region,
                provider=self.PROVIDER_TYPE,
                instance_type=droplet.size_slug,
            ))
        return results

    def get_instance_state(
        self, instance_id: str, region: str,
    ) -> InstanceState:
        """Get the current power state of a droplet."""
        client = self._get_client()
        droplet = client.get_droplet(instance_id)
        return self._map_state(droplet.status)

    def start_instance(self, instance_id: str, region: str) -> bool:
        """Power on a droplet. Returns True if successful or already running."""
        try:
            client = self._get_client()
            droplet = client.get_droplet(instance_id)
            if droplet.status == "active":
                return True  # Already running — idempotent
            client.power_on(instance_id)
            return True
        except Exception:
            return False

    def stop_instance(self, instance_id: str, region: str) -> bool:
        """Shut down a droplet. Returns True if successful or already stopped."""
        try:
            client = self._get_client()
            droplet = client.get_droplet(instance_id)
            if droplet.status == "off":
                return True  # Already stopped — idempotent
            client.shutdown(instance_id)
            return True
        except Exception:
            return False

    # -- Helpers --

    def _get_client(self):
        """Create an API client from stored credentials."""
        import digitalocean
        return digitalocean.Client(token=self.credentials.api_token)

    @staticmethod
    def _map_state(status: str) -> InstanceState:
        """Map provider-specific status to normalized InstanceState."""
        mapping = {
            "active": InstanceState.RUNNING,
            "off": InstanceState.STOPPED,
            "archive": InstanceState.STOPPED,
        }
        return mapping.get(status, InstanceState.UNKNOWN)
```

:::tip
Look at the existing providers for real-world patterns: `aws_ec2.py` handles paginated API calls, `azure_vm.py` uses composite instance IDs (`resourceGroup/vmName`), and `gcp_compute.py` waits for long-running operations. Pick the one closest to your provider's API style.
:::

## Step 3: Register the provider

Open `app/providers/__init__.py` and make three changes:

**1. Import your provider and credentials:**

```python
from app.providers.digitalocean import DigitalOceanProvider
```

And in the models import block:

```python
from app.providers.models import (
    # ... existing imports ...
    DigitalOceanCredentials,
)
```

**2. Add to the registry list:**

```python
_PROVIDER_CLASSES: List[Type[CloudProvider]] = [
    AWSEC2Provider,
    AzureVMProvider,
    GCPComputeProvider,
    DigitalOceanProvider,      # ← add here
]
```

**3. Update `__all__`:**

```python
__all__ = [
    # ... existing entries ...
    'DigitalOceanProvider',
    'DigitalOceanCredentials',
]
```

That's it for the backend. The registry auto-generates the metadata API, and the frontend reads it on load.

## Step 4: Write tests

Create `tests/providers/test_digitalocean.py`. The pattern is to mock the cloud SDK and test all five methods plus error handling.

```python
import pytest
from unittest.mock import patch, MagicMock

from app.providers.models import DigitalOceanCredentials, InstanceState
from app.providers.digitalocean import DigitalOceanProvider


@pytest.fixture
def mock_do_client():
    mock_client = MagicMock()
    with patch(
        "app.providers.digitalocean.digitalocean.Client",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.fixture
def provider(mock_do_client):
    creds = DigitalOceanCredentials(api_token="test-token")
    return DigitalOceanProvider(creds)


class TestValidateCredentials:
    def test_success(self, provider, mock_do_client):
        mock_do_client.get_account.return_value = {"status": "active"}
        result = provider.validate_credentials()
        assert result.is_valid is True

    def test_auth_error(self, provider, mock_do_client):
        mock_do_client.get_account.side_effect = Exception("401 Unauthorized")
        result = provider.validate_credentials()
        assert result.is_valid is False

    def test_network_error(self, provider, mock_do_client):
        mock_do_client.get_account.side_effect = ConnectionError("timeout")
        result = provider.validate_credentials()
        assert result.is_valid is False


class TestListInstances:
    def test_returns_instances(self, provider, mock_do_client):
        # ... mock droplet list, assert InstanceInfo fields
        pass

    def test_empty(self, provider, mock_do_client):
        mock_do_client.list_droplets.return_value = []
        result = provider.list_instances()
        assert result == []

    def test_region_filter(self, provider, mock_do_client):
        # ... mock droplets in multiple regions, filter to one
        pass


class TestStartInstance:
    def test_success(self, provider, mock_do_client):
        # ... mock successful power_on
        pass

    def test_already_running(self, provider, mock_do_client):
        # ... mock droplet with status "active", should return True
        pass


class TestStopInstance:
    def test_success(self, provider, mock_do_client):
        # ... mock successful shutdown
        pass

    def test_already_stopped(self, provider, mock_do_client):
        # ... mock droplet with status "off", should return True
        pass
```

Minimum test coverage:

- `validate_credentials` — success, auth error, network error
- `list_instances` — with results, empty, region filter
- `start_instance` / `stop_instance` — success, already in target state, error
- `get_instance_state` — each mapped state

Run your tests:

```bash
poetry run pytest tests/providers/test_digitalocean.py -v
```

## Step 5: Add pricing support (optional)

The cost calculator uses the `instance_pricing` table to look up hourly rates by provider, region, and instance type. If pricing data is available for your provider, you can integrate it into `app/services/pricing_updater.py`.

This step is optional — the provider will work without it, but the cost calculator won't be able to estimate savings for its instances.

## Checklist

1. Add credentials dataclass to `app/providers/models.py`
2. Create provider module in `app/providers/`
3. Register in `app/providers/__init__.py`
4. Write tests in `tests/providers/`
5. Run `poetry run pytest tests/providers/` to verify
6. (Optional) Add pricing support in `app/services/pricing_updater.py`
