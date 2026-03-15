import uuid
from unittest.mock import patch, AsyncMock

from app.providers.models import ProviderValidationResult
from tests.conftest import make_organization, make_cloud_account

_TO_THREAD = "app.api.v1.endpoints.cloud_accounts.asyncio.to_thread"
_AWS_CREDS = {"access_key_id": "test", "secret_access_key": "secret", "region": "us-east-1"}


class TestCloudAccounts:
    async def test_create_admin(self, client, org_and_admin):
        _, _, headers = org_and_admin
        with patch(_TO_THREAD, new=AsyncMock(return_value=ProviderValidationResult(is_valid=True))):
            r = await client.post("/api/v1/cloud-accounts/", json={
                "name": "Prod AWS",
                "provider_type": "aws",
                "credentials": _AWS_CREDS,
            }, headers=headers)
        assert r.status_code == 201
        assert r.json()["name"] == "Prod AWS"
        assert "credentials_encrypted" not in r.json()

    async def test_create_viewer_rejected(self, client, viewer_headers):
        with patch(_TO_THREAD, new=AsyncMock(return_value=ProviderValidationResult(is_valid=True))):
            r = await client.post("/api/v1/cloud-accounts/", json={
                "name": "Nope",
                "provider_type": "aws",
                "credentials": _AWS_CREDS,
            }, headers=viewer_headers)
        assert r.status_code == 403

    async def test_create_invalid_creds(self, client, org_and_admin):
        _, _, headers = org_and_admin
        with patch(_TO_THREAD, new=AsyncMock(return_value=ProviderValidationResult(
                is_valid=False, error_message="bad key"))):
            r = await client.post("/api/v1/cloud-accounts/", json={
                "name": "Bad",
                "provider_type": "aws",
                "credentials": _AWS_CREDS,
            }, headers=headers)
        assert r.status_code == 400
        assert "bad key" in r.json()["detail"]

    async def test_create_invalid_provider_type(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/cloud-accounts/", json={
            "name": "Bad Type",
            "provider_type": "digitalocean",
            "credentials": {},
        }, headers=headers)
        assert r.status_code == 422

    async def test_list_scoped_to_org(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        # Another org's account — should not appear in listing
        other_org = await make_organization(db, name="Other", slug="other-ca")
        await make_cloud_account(db, other_org, name="Other Account")
        # This org's account
        await make_cloud_account(db, org, name="My Account")

        r = await client.get("/api/v1/cloud-accounts/", headers=headers)
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "My Account" in names
        assert "Other Account" not in names

    async def test_get(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org, name="Get Me")

        r = await client.get(f"/api/v1/cloud-accounts/{account.id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Get Me"

    async def test_update_name(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org, name="Old Name")

        r = await client.put(f"/api/v1/cloud-accounts/{account.id}",
                             json={"name": "New Name"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    async def test_delete(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org)

        r = await client.delete(f"/api/v1/cloud-accounts/{account.id}", headers=headers)
        assert r.status_code == 204

        r = await client.get(f"/api/v1/cloud-accounts/{account.id}", headers=headers)
        assert r.status_code == 404

    async def test_sync_not_found(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post(f"/api/v1/cloud-accounts/{uuid.uuid4()}/sync", headers=headers)
        assert r.status_code == 404
