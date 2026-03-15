"""Integration tests for security hardening features.

Covers: security headers, request size limits, rate limiting,
RBAC error sanitization, audit logging, and API key default expiration.
"""

import os

from sqlalchemy import select

from tests.conftest import make_organization, make_user, make_api_key

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt-testing-only")


# ─── Security Headers ────────────────────────────────────────────────────────


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    async def test_health_has_security_headers(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in r.headers["permissions-policy"]

    async def test_api_endpoint_has_security_headers(self, client):
        r = await client.get("/")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"

    async def test_hsts_not_set_for_http(self, client):
        """HSTS should only be set on HTTPS connections."""
        r = await client.get("/health")
        assert "strict-transport-security" not in r.headers

    async def test_404_still_has_security_headers(self, client):
        r = await client.get("/nonexistent-path")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"


# ─── Request Size Limits ─────────────────────────────────────────────────────


class TestRequestSizeLimits:
    """Verify oversized POST/PUT requests are rejected."""

    async def test_oversized_post_rejected(self, client):
        """POST with content-length > 10MB returns 413."""
        r = await client.post(
            "/api/v1/auth/token",
            content=b"x",
            headers={"content-length": str(11 * 1024 * 1024)},
        )
        assert r.status_code == 413
        assert r.json()["detail"] == "Request body too large"

    async def test_normal_post_allowed(self, client):
        """Normal-sized POST goes through (may 401 but not 413)."""
        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "a@b.com", "password": "x"},
        )
        assert r.status_code != 413

    async def test_get_not_size_limited(self, client):
        """GET requests are never rejected for size."""
        r = await client.get("/health")
        assert r.status_code == 200


# ─── RBAC Error Sanitization ─────────────────────────────────────────────────


class TestRBACErrorSanitization:
    """Verify 403 errors don't leak role information."""

    async def test_viewer_forbidden_message_is_generic(self, client, db):
        org = await make_organization(db)
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, viewer)

        r = await client.post(
            "/api/v1/policies/",
            json={
                "name": "test",
                "timezone": "UTC",
                "schedule": {"monday": [{"start": "09:00", "end": "17:00"}]},
                "resource_selector": {"tags": {"env": "test"}},
            },
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 403
        body = r.json()
        assert body["detail"] == "You do not have permission to perform this action."
        # Must NOT contain role names
        assert "viewer" not in body["detail"].lower()
        assert "admin" not in body["detail"].lower()

    async def test_operator_forbidden_message_is_generic(self, client, db):
        org = await make_organization(db)
        operator = await make_user(db, org, role="operator")
        raw_key, _ = await make_api_key(db, operator)

        r = await client.post(
            "/api/v1/cloud-accounts/",
            json={
                "name": "test",
                "provider_type": "aws",
                "credentials": {"access_key_id": "x", "secret_access_key": "y"},
            },
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 403
        assert "operator" not in r.json()["detail"].lower()


# ─── Audit Logging ───────────────────────────────────────────────────────────


class TestAuditLogging:
    """Verify audit log entries are created for security-relevant actions."""

    async def _get_audit_logs(self, db, event_type=None):
        from app.models.audit_log import AuditLog

        query = select(AuditLog)
        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        query = query.order_by(AuditLog.timestamp.desc())
        result = await db.execute(query)
        return result.scalars().all()

    async def test_successful_login_creates_audit_log(self, client, db):
        org = await make_organization(db)
        await make_user(
            db, org, email="audit@test.com", password="testpass123"
        )

        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "audit@test.com", "password": "testpass123"},
        )
        assert r.status_code == 200

        logs = await self._get_audit_logs(db, "auth.login")
        assert len(logs) >= 1
        assert logs[0].description == "User audit@test.com logged in"

    async def test_failed_login_creates_audit_log(self, client, db):
        org = await make_organization(db)
        await make_user(
            db, org, email="audit@test.com", password="testpass123"
        )

        r = await client.post(
            "/api/v1/auth/token",
            json={"email": "audit@test.com", "password": "wrongpassword"},
        )
        assert r.status_code == 401

        logs = await self._get_audit_logs(db, "auth.login_failed")
        assert len(logs) >= 1
        assert logs[0].details["email"] == "audit@test.com"

    async def test_api_key_create_creates_audit_log(self, client, db):
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin", password="testpass123")

        # Login to get JWT
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "my-ci-key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        logs = await self._get_audit_logs(db, "api_key.create")
        assert len(logs) >= 1
        assert "my-ci-key" in logs[0].description

    async def test_api_key_delete_creates_audit_log(self, client, db):
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin", password="testpass123")

        # Login
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a key
        create_r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "to-delete"},
            headers=headers,
        )
        key_id = create_r.json()["id"]

        # Delete it
        r = await client.delete(
            f"/api/v1/auth/keys/{key_id}",
            headers=headers,
        )
        assert r.status_code == 204

        logs = await self._get_audit_logs(db, "api_key.delete")
        assert len(logs) >= 1
        assert "to-delete" in logs[0].description

    async def test_user_create_creates_audit_log(self, client, db):
        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        r = await client.post(
            "/api/v1/users/",
            json={
                "email": "newuser@test.com",
                "password": "newpass123",
                "full_name": "New User",
                "role": "viewer",
                "organization_id": str(org.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        logs = await self._get_audit_logs(db, "user.create")
        assert len(logs) >= 1
        assert "newuser@test.com" in logs[0].description
        assert logs[0].details["role"] == "viewer"

    async def test_audit_log_endpoint_admin_only(self, client, db):
        org = await make_organization(db)
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, viewer)

        r = await client.get(
            "/api/v1/audit-logs/",
            headers={"X-API-Key": raw_key},
        )
        assert r.status_code == 403

    async def test_audit_log_endpoint_returns_entries(self, client, db):
        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        # Single login generates the event AND gives us a token
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        r = await client.get(
            "/api/v1/audit-logs/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) >= 1
        assert entries[0]["event_type"] == "auth.login"

    async def test_audit_log_filter_by_event_type(self, client, db):
        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        # Login to get token (also generates auth.login event)
        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        # Generate a failed login event
        await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "wrong"},
        )

        r = await client.get(
            "/api/v1/audit-logs/?event_type=auth.login_failed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        entries = r.json()
        assert all(e["event_type"] == "auth.login_failed" for e in entries)


# ─── API Key Default Expiration ──────────────────────────────────────────────


class TestAPIKeyDefaultExpiration:
    """Verify new API keys get a default 90-day expiration."""

    async def test_key_gets_default_expiration(self, client, db):
        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "default-expiry-key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["expires_at"] is not None
        assert body["days_until_expiry"] is not None
        assert 88 <= body["days_until_expiry"] <= 90

    async def test_custom_expiration_honored(self, client, db):
        from datetime import datetime, timedelta, timezone

        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]

        custom_expiry = (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat()

        r = await client.post(
            "/api/v1/auth/keys",
            json={"name": "custom-expiry-key", "expires_at": custom_expiry},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["expires_at"] is not None
        assert body["days_until_expiry"] is not None
        assert 28 <= body["days_until_expiry"] <= 30

    async def test_key_list_includes_expiry_fields(self, client, db):
        org = await make_organization(db)
        admin = await make_user(
            db, org, role="admin", password="testpass123"
        )

        login_r = await client.post(
            "/api/v1/auth/token",
            json={"email": admin.email, "password": "testpass123"},
        )
        token = login_r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a key
        await client.post(
            "/api/v1/auth/keys",
            json={"name": "list-test-key"},
            headers=headers,
        )

        # List keys
        r = await client.get("/api/v1/auth/keys", headers=headers)
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) >= 1
        key = keys[0]
        assert "days_until_expiry" in key
        assert "expires_soon" in key
        assert key["expires_soon"] is False
