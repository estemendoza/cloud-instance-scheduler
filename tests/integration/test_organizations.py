import uuid

from tests.conftest import make_organization, make_user, make_api_key


class TestOrganizations:
    async def test_create_bootstrap(self, client):
        """First organization can be created without auth (bootstrap)."""
        r = await client.post("/api/v1/organizations/", json={"name": "My Org", "slug": "my-org"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "My Org"
        assert body["slug"] == "my-org"
        assert "id" in body

    async def test_create_blocked_after_bootstrap(self, client, db):
        """Organization creation is blocked after first org exists."""
        # Create first org via DB (simulating bootstrap already happened)
        await make_organization(db, name="Existing Org", slug="existing")

        # Attempt to create another org via API should be blocked
        r = await client.post("/api/v1/organizations/", json={"name": "New Org", "slug": "new-org"})
        assert r.status_code == 403
        assert "disabled" in r.json()["detail"].lower()

    async def test_list(self, client, db):
        """List all organizations."""
        await make_organization(db, name="Org 1", slug="org-list-1")
        await make_organization(db, name="Org 2", slug="org-list-2")

        r = await client.get("/api/v1/organizations/")
        assert r.status_code == 200
        slugs = {o["slug"] for o in r.json()}
        assert "org-list-1" in slugs
        assert "org-list-2" in slugs

    async def test_get_by_id(self, client, db):
        """Get organization by ID."""
        org = await make_organization(db, name="Get Me", slug="get-me")

        r = await client.get(f"/api/v1/organizations/{org.id}")
        assert r.status_code == 200
        assert r.json()["slug"] == "get-me"

    async def test_get_not_found(self, client):
        """Get nonexistent organization returns 404."""
        r = await client.get(f"/api/v1/organizations/{uuid.uuid4()}")
        assert r.status_code == 404


class TestOrganizationsUpdate:
    """Tests for PUT /api/v1/organizations/{org_id} endpoint."""

    async def test_admin_can_update_name(self, client, db):
        """Admin can update their organization's name."""
        org = await make_organization(db, name="Old Name", slug="update-test-1")
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"name": "New Name"}
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"
        assert r.json()["slug"] == "update-test-1"

    async def test_admin_can_update_slug(self, client, db):
        """Admin can update their organization's slug."""
        org = await make_organization(db, name="Test Org", slug="old-slug")
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"slug": "new-slug"}
        )
        assert r.status_code == 200
        assert r.json()["slug"] == "new-slug"

    async def test_admin_can_update_both(self, client, db):
        """Admin can update both name and slug at once."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"name": "Updated Name", "slug": "updated-slug"}
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"
        assert r.json()["slug"] == "updated-slug"

    async def test_operator_cannot_update(self, client, db):
        """Operator cannot update organization (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        operator = await make_user(db, org, role="operator")
        raw_key, _ = await make_api_key(db, operator)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"name": "Hacked"}
        )
        assert r.status_code == 403

    async def test_viewer_cannot_update(self, client, db):
        """Viewer cannot update organization (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, viewer)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"name": "Hacked"}
        )
        assert r.status_code == 403

    async def test_cannot_update_other_org(self, client, db):
        """Admin cannot update another organization."""
        org1 = await make_organization(db, name="Org 1")
        org2 = await make_organization(db, name="Org 2")

        admin1 = await make_user(db, org1, role="admin")
        await make_user(db, org2, role="admin")
        raw_key, _ = await make_api_key(db, admin1)

        r = await client.put(
            f"/api/v1/organizations/{org2.id}",
            headers={"X-API-Key": raw_key},
            json={"name": "Hacked"}
        )
        assert r.status_code == 403

    async def test_slug_must_be_unique(self, client, db):
        """Cannot update slug to one already in use."""
        org1 = await make_organization(db, slug="existing-slug")
        org2 = await make_organization(db, slug="my-slug")

        await make_user(db, org1, role="admin")
        admin2 = await make_user(db, org2, role="admin")
        raw_key, _ = await make_api_key(db, admin2)

        r = await client.put(
            f"/api/v1/organizations/{org2.id}",
            headers={"X-API-Key": raw_key},
            json={"slug": "existing-slug"}
        )
        assert r.status_code == 409
        assert "slug" in r.json()["detail"].lower()

    async def test_can_update_slug_to_same_value(self, client, db):
        """Updating slug to the same value should succeed."""
        org = await make_organization(db, slug="same-slug")
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/organizations/{org.id}",
            headers={"X-API-Key": raw_key},
            json={"slug": "same-slug"}
        )
        assert r.status_code == 200
        assert r.json()["slug"] == "same-slug"

    async def test_update_nonexistent_org(self, client, db):
        """Updating a nonexistent organization returns 404."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/organizations/{uuid.uuid4()}",
            headers={"X-API-Key": raw_key},
            json={"name": "Test"}
        )
        # This returns 403 because it's not the user's org, not 404
        assert r.status_code == 403

    async def test_update_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.put(
            f"/api/v1/organizations/{uuid.uuid4()}",
            json={"name": "Test"}
        )
        assert r.status_code == 401
