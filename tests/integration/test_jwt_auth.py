"""Tests for JWT authentication endpoints."""

import os
import uuid

from tests.conftest import make_organization, make_user


# Set JWT secret for tests
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt-testing-only")


class TestJWTLogin:
    """Tests for POST /api/v1/auth/token endpoint."""

    async def test_login_returns_tokens(self, client, db):
        """Successful login returns access and refresh tokens."""
        org = await make_organization(db)
        user = await make_user(db, org, email="test@example.com", password="testpass123")

        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "testpass123"}
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "test@example.com"
        assert body["user"]["id"] == str(user.id)

    async def test_login_invalid_password(self, client, db):
        """Login with wrong password returns 401."""
        org = await make_organization(db)
        await make_user(db, org, email="test@example.com", password="testpass123")

        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "wrongpassword"}
        )
        assert r.status_code == 401

    async def test_login_nonexistent_user(self, client):
        """Login with nonexistent email returns 401."""
        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "nobody@example.com", "password": "testpass123"}
        )
        assert r.status_code == 401

    async def test_login_inactive_user(self, client, db):
        """Login with inactive user returns 401."""
        org = await make_organization(db)
        user = await make_user(db, org, email="inactive@example.com", password="testpass123")
        user.is_active = False
        await db.commit()

        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "inactive@example.com", "password": "testpass123"}
        )
        assert r.status_code == 401


class TestJWTRefresh:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    async def test_refresh_returns_new_access_token(self, client, db):
        """Valid refresh token returns new access token."""
        org = await make_organization(db)
        await make_user(db, org, email="test@example.com", password="testpass123")

        # First login to get tokens
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "testpass123"}
        )
        refresh_token = login_r.json()["refresh_token"]

        # Use refresh token to get new access token
        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, client):
        """Invalid refresh token returns 401."""
        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        assert r.status_code == 401

    async def test_refresh_with_access_token_fails(self, client, db):
        """Using access token as refresh token fails."""
        org = await make_organization(db)
        await make_user(db, org, email="test@example.com", password="testpass123")

        # Get tokens
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "testpass123"}
        )
        access_token = login_r.json()["access_token"]

        # Try to use access token as refresh token
        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token}
        )
        assert r.status_code == 401


class TestJWTBootstrap:
    """Tests for POST /api/v1/auth/bootstrap endpoint."""

    async def test_bootstrap_returns_tokens(self, client, db):
        """Bootstrap for first user returns JWT tokens."""
        org = await make_organization(db)
        user = await make_user(db, org, email="admin@example.com", password="testpass123")

        r = await client.post(
            "/api/v1/auth/bootstrap",
            json={"user_id": str(user.id)}
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "admin@example.com"

    async def test_bootstrap_fails_with_multiple_users(self, client, db):
        """Bootstrap fails when org has multiple users."""
        org = await make_organization(db)
        user1 = await make_user(db, org, email="admin@example.com")
        await make_user(db, org, email="user2@example.com")

        r = await client.post(
            "/api/v1/auth/bootstrap",
            json={"user_id": str(user1.id)}
        )
        assert r.status_code == 403

    async def test_bootstrap_fails_with_existing_keys(self, client, db):
        """Bootstrap fails when user already has API keys."""
        from tests.conftest import make_api_key

        org = await make_organization(db)
        user = await make_user(db, org, email="admin@example.com")
        await make_api_key(db, user)

        r = await client.post(
            "/api/v1/auth/bootstrap",
            json={"user_id": str(user.id)}
        )
        assert r.status_code == 403

    async def test_bootstrap_nonexistent_user(self, client):
        """Bootstrap for nonexistent user returns 404."""
        r = await client.post(
            "/api/v1/auth/bootstrap",
            json={"user_id": str(uuid.uuid4())}
        )
        assert r.status_code == 404


class TestJWTProtectedEndpoints:
    """Tests for accessing protected endpoints with JWT."""

    async def test_access_with_bearer_token(self, client, db):
        """Can access protected endpoint with Bearer token."""
        org = await make_organization(db)
        await make_user(db, org, email="test@example.com", password="testpass123", role="admin")

        # Login to get tokens
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "testpass123"}
        )
        access_token = login_r.json()["access_token"]

        # Access protected endpoint
        r = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert r.status_code == 200
        assert r.json()["email"] == "test@example.com"

    async def test_access_with_invalid_bearer_token(self, client):
        """Invalid Bearer token returns 401."""
        r = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert r.status_code == 401

    async def test_access_without_auth(self, client):
        """No auth returns 401."""
        r = await client.get("/api/v1/users/me")
        assert r.status_code == 401


class TestDualAuthSupport:
    """Tests for dual authentication (JWT + API Key)."""

    async def test_api_key_still_works(self, client, db):
        """API key authentication still works alongside JWT."""
        from tests.conftest import make_api_key

        org = await make_organization(db)
        user = await make_user(db, org, email="test@example.com", role="admin")
        raw_key, _ = await make_api_key(db, user)

        r = await client.get(
            "/api/v1/users/me",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 200
        assert r.json()["email"] == "test@example.com"

    async def test_jwt_preferred_over_api_key(self, client, db):
        """When both are provided, JWT is used (and should succeed)."""
        from tests.conftest import make_api_key

        org = await make_organization(db)
        user = await make_user(db, org, email="test@example.com", password="testpass123", role="admin")
        raw_key, _ = await make_api_key(db, user)

        # Get JWT token
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "testpass123"}
        )
        access_token = login_r.json()["access_token"]

        # Send both - should work
        r = await client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-API-Key": raw_key,
            }
        )
        assert r.status_code == 200
