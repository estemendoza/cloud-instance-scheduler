"""Tests for self-service profile endpoints and non-admin API key creation."""

from tests.conftest import make_organization, make_user, make_api_key


class TestProfileUpdate:
    """PUT /users/me — update own profile."""

    async def test_update_full_name(self, client, db, org_and_admin):
        _, admin, headers = org_and_admin
        r = await client.put(
            "/api/v1/users/me",
            json={"full_name": "New Name"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "New Name"

    async def test_viewer_can_update_own_profile(self, client, db, viewer_headers):
        r = await client.put(
            "/api/v1/users/me",
            json={"full_name": "Viewer Updated"},
            headers=viewer_headers,
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Viewer Updated"

    async def test_unauthenticated_rejected(self, client):
        r = await client.put(
            "/api/v1/users/me",
            json={"full_name": "Nope"},
        )
        assert r.status_code in (401, 403)


class TestPasswordChange:
    """PUT /users/me/password — change own password."""

    async def test_change_password_success(self, client, db):
        org = await make_organization(db)
        user = await make_user(db, org, password="oldpass123")
        raw_key, _ = await make_api_key(db, user)
        headers = {"X-API-Key": raw_key}

        r = await client.put(
            "/api/v1/users/me/password",
            json={"current_password": "oldpass123", "new_password": "newpass456"},
            headers=headers,
        )
        assert r.status_code == 204

        # Verify new password works for login
        r = await client.post(
            "/api/v1/auth/token",
            json={"email": user.email, "password": "newpass456"},
        )
        assert r.status_code == 200

    async def test_change_password_wrong_current(self, client, db, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.put(
            "/api/v1/users/me/password",
            json={"current_password": "wrong", "new_password": "newpass456"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "incorrect" in r.json()["detail"]

    async def test_unauthenticated_rejected(self, client):
        r = await client.put(
            "/api/v1/users/me/password",
            json={"current_password": "a", "new_password": "b"},
        )
        assert r.status_code in (401, 403)


class TestApiKeyCreatePermissions:
    """POST /auth/keys — any authenticated user can create API keys."""

    async def test_operator_can_create_key(self, client, db, operator_headers):
        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "operator-key"},
            headers=operator_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "operator-key"
        assert "key" in data

    async def test_viewer_can_create_key(self, client, db, viewer_headers):
        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "viewer-key"},
            headers=viewer_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "viewer-key"

    async def test_unauthenticated_rejected(self, client):
        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "anon-key"},
        )
        assert r.status_code in (401, 403)
