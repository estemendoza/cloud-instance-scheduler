import uuid

from tests.conftest import make_organization, make_user, make_api_key


class TestAPIKeysList:
    """Tests for GET /api/v1/auth/keys endpoint."""

    async def test_list_own_keys(self, client, db):
        """User can list their own API keys."""
        org = await make_organization(db)
        user = await make_user(db, org, role="admin")
        raw_key1, db_key1 = await make_api_key(db, user)
        raw_key2, _ = await make_api_key(db, user)

        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key1})
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) == 2
        prefixes = {k["prefix"] for k in keys}
        assert db_key1.prefix in prefixes

    async def test_list_keys_empty(self, client, db):
        """User with only one key sees just that key."""
        org = await make_organization(db)
        user = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, user)

        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) == 1

    async def test_list_keys_does_not_include_other_users_keys(self, client, db):
        """Users cannot see API keys of other users."""
        org = await make_organization(db)
        user1 = await make_user(db, org, role="admin")
        user2 = await make_user(db, org, role="operator")

        raw_key1, db_key1 = await make_api_key(db, user1)
        _, db_key2 = await make_api_key(db, user2)

        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key1})
        assert r.status_code == 200
        keys = r.json()
        prefixes = {k["prefix"] for k in keys}
        assert db_key1.prefix in prefixes
        assert db_key2.prefix not in prefixes

    async def test_list_keys_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.get("/api/v1/auth/keys")
        assert r.status_code == 401

    async def test_list_keys_response_format(self, client, db):
        """Response includes expected fields."""
        org = await make_organization(db)
        user = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, user)

        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) == 1
        key = keys[0]
        assert "id" in key
        assert "prefix" in key
        assert "name" in key
        assert "created_at" in key
        # Should NOT include the actual key hash
        assert "key_hash" not in key
        assert "key" not in key


class TestAPIKeysDelete:
    """Tests for DELETE /api/v1/auth/keys/{key_id} endpoint."""

    async def test_delete_own_key(self, client, db):
        """User can delete their own API key."""
        org = await make_organization(db)
        user = await make_user(db, org, role="admin")
        raw_key1, _ = await make_api_key(db, user)
        raw_key2, db_key2 = await make_api_key(db, user)

        # Delete the second key using the first key for auth
        r = await client.delete(
            f"/api/v1/auth/keys/{db_key2.id}",
            headers={"X-API-Key": raw_key1}
        )
        assert r.status_code == 204

        # Verify it's deleted
        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key1})
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) == 1

    async def test_cannot_delete_other_users_key(self, client, db):
        """User cannot delete another user's API key."""
        org = await make_organization(db)
        user1 = await make_user(db, org, role="admin")
        user2 = await make_user(db, org, role="operator")

        raw_key1, _ = await make_api_key(db, user1)
        _, db_key2 = await make_api_key(db, user2)

        r = await client.delete(
            f"/api/v1/auth/keys/{db_key2.id}",
            headers={"X-API-Key": raw_key1}
        )
        assert r.status_code == 404

    async def test_delete_nonexistent_key(self, client, db):
        """Deleting a nonexistent key returns 404."""
        org = await make_organization(db)
        user = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, user)

        r = await client.delete(
            f"/api/v1/auth/keys/{uuid.uuid4()}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 404

    async def test_delete_key_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.delete(f"/api/v1/auth/keys/{uuid.uuid4()}")
        assert r.status_code == 401

    async def test_deleted_key_no_longer_works(self, client, db):
        """A deleted API key can no longer be used for authentication."""
        org = await make_organization(db)
        user = await make_user(db, org, role="admin")
        raw_key1, db_key1 = await make_api_key(db, user)
        raw_key2, _ = await make_api_key(db, user)

        # Delete the first key using the second key
        r = await client.delete(
            f"/api/v1/auth/keys/{db_key1.id}",
            headers={"X-API-Key": raw_key2}
        )
        assert r.status_code == 204

        # The deleted key should no longer work
        r = await client.get("/api/v1/auth/keys", headers={"X-API-Key": raw_key1})
        assert r.status_code == 401
