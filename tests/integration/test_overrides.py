from datetime import datetime, timedelta, timezone

from tests.conftest import (
    make_cloud_account, make_resource, make_organization, make_override,
)


class TestOverrides:
    async def test_create_operator(self, client, db, org_and_admin, operator_headers):
        org, _, _ = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        r = await client.post("/api/v1/overrides/", json={
            "resource_id": str(resource.id),
            "desired_state": "RUNNING",
            "expires_at": future,
            "reason": "maintenance",
        }, headers=operator_headers)
        assert r.status_code == 201
        assert r.json()["desired_state"] == "RUNNING"

    async def test_create_viewer_rejected(self, client, db, org_and_admin, viewer_headers):
        org, _, _ = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        r = await client.post("/api/v1/overrides/", json={
            "resource_id": str(resource.id),
            "desired_state": "STOPPED",
            "expires_at": future,
        }, headers=viewer_headers)
        assert r.status_code == 403

    async def test_create_resource_not_in_org(self, client, db, org_and_admin):
        _, _, headers = org_and_admin
        # Resource in a different org
        other_org = await make_organization(db, name="Other Org", slug="other-ov")
        other_ca = await make_cloud_account(db, other_org, name="Other CA")
        other_resource = await make_resource(db, other_org, other_ca)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        r = await client.post("/api/v1/overrides/", json={
            "resource_id": str(other_resource.id),
            "desired_state": "RUNNING",
            "expires_at": future,
        }, headers=headers)
        assert r.status_code == 404

    async def test_create_invalid_desired_state(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        r = await client.post("/api/v1/overrides/", json={
            "resource_id": str(resource.id),
            "desired_state": "INVALID",
            "expires_at": future,
        }, headers=headers)
        assert r.status_code == 422

    async def test_list_excludes_expired(self, client, db, org_and_admin):
        org, admin, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)

        # Active override (future expiry)
        await make_override(db, org, resource, desired_state="RUNNING",
                            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                            user=admin)
        # Expired override (past expiry)
        await make_override(db, org, resource, desired_state="STOPPED",
                            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
                            user=admin)

        r = await client.get("/api/v1/overrides/", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["desired_state"] == "RUNNING"

    async def test_delete(self, client, db, org_and_admin):
        org, admin, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        override = await make_override(db, org, resource, user=admin)

        r = await client.delete(f"/api/v1/overrides/{override.id}", headers=headers)
        assert r.status_code == 204

        r = await client.get("/api/v1/overrides/", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 0
