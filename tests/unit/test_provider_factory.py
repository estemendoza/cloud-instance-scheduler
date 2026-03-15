import pytest

from app.providers import (
    build_credentials, get_provider, get_valid_provider_types,
    get_non_secret_keys, get_all_provider_metadata,
)
from app.providers.models import AWSCredentials, AzureCredentials, GCPCredentials
from app.providers.aws_ec2 import AWSEC2Provider
from app.providers.azure_vm import AzureVMProvider
from app.providers.gcp_compute import GCPComputeProvider


class TestBuildCredentials:
    def test_aws(self):
        creds = build_credentials("aws", {
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "secret",
            "region": "us-east-1",
        })
        assert isinstance(creds, AWSCredentials)
        assert creds.access_key_id == "AKIA_TEST"
        assert creds.region == "us-east-1"

    def test_azure(self):
        creds = build_credentials("azure", {
            "subscription_id": "sub-123",
            "tenant_id": "tenant-123",
            "client_id": "client-123",
            "client_secret": "secret",
        })
        assert isinstance(creds, AzureCredentials)

    def test_gcp(self):
        creds = build_credentials("gcp", {
            "project_id": "my-project",
            "service_account_json": '{"type": "service_account"}',
        })
        assert isinstance(creds, GCPCredentials)

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            build_credentials("digitalocean", {})

    def test_case_insensitive(self):
        creds = build_credentials("AWS", {
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "secret",
            "region": "us-east-1",
        })
        assert isinstance(creds, AWSCredentials)


class TestGetProvider:
    def test_aws(self):
        creds = AWSCredentials(
            access_key_id="AKIA_TEST",
            secret_access_key="secret",
            region="us-east-1",
        )
        provider = get_provider("aws", creds)
        assert isinstance(provider, AWSEC2Provider)

    def test_azure(self):
        creds = AzureCredentials(
            subscription_id="s", tenant_id="t",
            client_id="c", client_secret="cs",
        )
        provider = get_provider("azure", creds)
        assert isinstance(provider, AzureVMProvider)

    def test_gcp(self):
        creds = GCPCredentials(
            project_id="proj",
            service_account_json='{"type": "service_account"}',
        )
        provider = get_provider("gcp", creds)
        assert isinstance(provider, GCPComputeProvider)

    def test_unsupported_raises(self):
        creds = AWSCredentials(
            access_key_id="x", secret_access_key="y",
        )
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_provider("digitalocean", creds)


class TestGetValidProviderTypes:
    def test_returns_all_registered(self):
        types = get_valid_provider_types()
        assert "aws" in types
        assert "azure" in types
        assert "gcp" in types

    def test_returns_list(self):
        assert isinstance(get_valid_provider_types(), list)


class TestGetNonSecretKeys:
    def test_aws(self):
        keys = get_non_secret_keys("aws")
        assert "access_key_id" in keys
        assert "secret_access_key" not in keys

    def test_azure(self):
        keys = get_non_secret_keys("azure")
        assert "subscription_id" in keys
        assert "tenant_id" in keys
        assert "client_id" in keys
        assert "client_secret" not in keys

    def test_gcp(self):
        keys = get_non_secret_keys("gcp")
        assert "project_id" in keys
        assert "service_account_json" not in keys

    def test_unknown_provider(self):
        keys = get_non_secret_keys("unknown")
        assert keys == set()


class TestGetAllProviderMetadata:
    def test_returns_all_providers(self):
        metadata = get_all_provider_metadata()
        types = [m["provider_type"] for m in metadata]
        assert "aws" in types
        assert "azure" in types
        assert "gcp" in types

    def test_metadata_structure(self):
        metadata = get_all_provider_metadata()
        for m in metadata:
            assert "provider_type" in m
            assert "display_name" in m
            assert "color" in m
            assert "region_label" in m
            assert "credential_fields" in m
            assert "regions" in m
            assert len(m["credential_fields"]) > 0
            assert len(m["regions"]) > 0

    def test_credential_field_structure(self):
        metadata = get_all_provider_metadata()
        for m in metadata:
            for field in m["credential_fields"]:
                assert "key" in field
                assert "label" in field
                assert "type" in field
                assert "required" in field
                assert "secret" in field
