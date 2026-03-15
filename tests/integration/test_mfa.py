"""Tests for MFA (Multi-Factor Authentication) endpoints."""

import pyotp

from tests.conftest import make_organization, make_user, make_api_key


async def _jwt_login(client, email, password):
    """Helper: login and return the response JSON."""
    r = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    return r


async def _setup_user_with_key(db, org=None, role="admin"):
    """Helper: create user + API key, return (user, headers)."""
    if org is None:
        org = await make_organization(db)
    user = await make_user(db, org, role=role)
    raw_key, _ = await make_api_key(db, user)
    return user, {"X-API-Key": raw_key}


class TestMfaStatus:
    async def test_status_default_disabled(self, client, db):
        _, headers = await _setup_user_with_key(db)
        r = await client.get("/api/v1/auth/mfa/status", headers=headers)
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    async def test_status_unauthenticated(self, client):
        r = await client.get("/api/v1/auth/mfa/status")
        assert r.status_code in (401, 403)


class TestMfaSetup:
    async def test_setup_returns_secret_and_uri(self, client, db):
        user, headers = await _setup_user_with_key(db)
        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        # @ is URL-encoded as %40 in otpauth URIs
        from urllib.parse import unquote
        assert user.email in unquote(data["provisioning_uri"])

    async def test_setup_already_enabled_rejected(self, client, db):
        user, headers = await _setup_user_with_key(db)

        # Setup + verify to enable MFA
        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)
        await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": totp.now()},
            headers=headers,
        )

        # Second setup should fail
        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert r.status_code == 400
        assert "already enabled" in r.json()["detail"]


class TestMfaVerify:
    async def test_verify_valid_code_enables_mfa(self, client, db):
        _, headers = await _setup_user_with_key(db)

        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)

        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": totp.now()},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        # Confirm status reflects change
        r = await client.get("/api/v1/auth/mfa/status", headers=headers)
        assert r.json()["enabled"] is True

    async def test_verify_invalid_code_rejected(self, client, db):
        _, headers = await _setup_user_with_key(db)
        await client.post("/api/v1/auth/mfa/setup", headers=headers)

        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": "000000"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "Invalid" in r.json()["detail"]

    async def test_verify_without_setup_rejected(self, client, db):
        _, headers = await _setup_user_with_key(db)

        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": "123456"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "not been initiated" in r.json()["detail"]


class TestMfaDisable:
    async def _enable_mfa(self, client, headers):
        """Setup + verify MFA, return the TOTP secret."""
        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)
        await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": totp.now()},
            headers=headers,
        )
        return secret

    async def test_disable_with_valid_password_and_code(self, client, db):
        password = "testpass123"
        org = await make_organization(db)
        user = await make_user(db, org, password=password)
        raw_key, _ = await make_api_key(db, user)
        headers = {"X-API-Key": raw_key}

        secret = await self._enable_mfa(client, headers)
        totp = pyotp.TOTP(secret)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            json={"password": password, "code": totp.now()},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        # Confirm status reflects change
        r = await client.get("/api/v1/auth/mfa/status", headers=headers)
        assert r.json()["enabled"] is False

    async def test_disable_wrong_password_rejected(self, client, db):
        _, headers = await _setup_user_with_key(db)
        secret = await self._enable_mfa(client, headers)
        totp = pyotp.TOTP(secret)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            json={"password": "wrongpassword", "code": totp.now()},
            headers=headers,
        )
        assert r.status_code == 400
        assert "Invalid password" in r.json()["detail"]

    async def test_disable_wrong_code_rejected(self, client, db):
        password = "testpass123"
        org = await make_organization(db)
        user = await make_user(db, org, password=password)
        raw_key, _ = await make_api_key(db, user)
        headers = {"X-API-Key": raw_key}

        await self._enable_mfa(client, headers)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            json={"password": password, "code": "000000"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "Invalid verification code" in r.json()["detail"]

    async def test_disable_when_not_enabled_rejected(self, client, db):
        _, headers = await _setup_user_with_key(db)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            json={"password": "testpass123", "code": "123456"},
            headers=headers,
        )
        assert r.status_code == 400
        assert "not enabled" in r.json()["detail"]


class TestMfaValidate:
    """Tests for the MFA validation step during login."""

    async def _setup_mfa_user(self, client, db):
        """Create a user with MFA enabled. Return (user, secret, password)."""
        password = "testpass123"
        org = await make_organization(db)
        user = await make_user(db, org, password=password)
        raw_key, _ = await make_api_key(db, user)
        headers = {"X-API-Key": raw_key}

        r = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = r.json()["secret"]
        totp = pyotp.TOTP(secret)
        await client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": totp.now()},
            headers=headers,
        )
        return user, secret, password

    async def test_login_returns_mfa_challenge(self, client, db):
        user, _, password = await self._setup_mfa_user(client, db)

        r = await _jwt_login(client, user.email, password)
        assert r.status_code == 200
        data = r.json()
        assert data["mfa_required"] is True
        assert "mfa_token" in data

    async def test_validate_valid_code_returns_tokens(self, client, db):
        user, secret, password = await self._setup_mfa_user(client, db)

        # Login to get MFA token
        r = await _jwt_login(client, user.email, password)
        mfa_token = r.json()["mfa_token"]

        # Validate MFA
        totp = pyotp.TOTP(secret)
        r = await client.post(
            "/api/v1/auth/mfa/validate",
            json={"mfa_token": mfa_token, "code": totp.now()},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == user.email

    async def test_validate_invalid_code_rejected(self, client, db):
        user, _, password = await self._setup_mfa_user(client, db)

        r = await _jwt_login(client, user.email, password)
        mfa_token = r.json()["mfa_token"]

        r = await client.post(
            "/api/v1/auth/mfa/validate",
            json={"mfa_token": mfa_token, "code": "000000"},
        )
        assert r.status_code == 401

    async def test_validate_invalid_token_rejected(self, client, db):
        r = await client.post(
            "/api/v1/auth/mfa/validate",
            json={"mfa_token": "invalid-token", "code": "123456"},
        )
        assert r.status_code == 401
