from tests.conftest import make_organization, make_user


class TestBootstrap:
    async def test_full_happy_path(self, client):
        # 1. Create org (unauthenticated)
        r = await client.post("/api/v1/organizations/", json={"name": "Boot Org", "slug": "boot-org"})
        assert r.status_code == 201
        org_id = r.json()["id"]

        # 2. First user — admin, no auth required
        r = await client.post("/api/v1/users/", json={
            "email": "admin@boot.com",
            "password": "pass123",
            "role": "admin",
            "organization_id": org_id,
        })
        assert r.status_code == 200
        user_id = r.json()["id"]

        # 3. Bootstrap key (org has exactly 1 user with 0 keys)
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_id})
        assert r.status_code == 200
        key = r.json()["key"]
        assert len(key) == 32

        # 4. Use key to access authenticated endpoint
        r = await client.get("/api/v1/users/me", headers={"X-API-Key": key})
        assert r.status_code == 200
        assert r.json()["id"] == user_id

    async def test_first_user_must_be_admin(self, client):
        r = await client.post("/api/v1/organizations/", json={"name": "Org A", "slug": "must-admin"})
        org_id = r.json()["id"]

        r = await client.post("/api/v1/users/", json={
            "email": "viewer@boot.com",
            "password": "pass",
            "role": "viewer",
            "organization_id": org_id,
        })
        assert r.status_code == 400
        assert "admin" in r.json()["detail"].lower()

    async def test_second_user_no_auth_rejected(self, client):
        r = await client.post("/api/v1/organizations/", json={"name": "Org B", "slug": "second-no-auth"})
        org_id = r.json()["id"]

        # First user (admin, no auth needed)
        r = await client.post("/api/v1/users/", json={
            "email": "admin-b@boot.com", "password": "pass", "role": "admin",
            "organization_id": org_id,
        })
        user_id = r.json()["id"]

        # Bootstrap key so first user is fully set up
        await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_id})

        # Second user without auth header -> 403
        r = await client.post("/api/v1/users/", json={
            "email": "nobody@boot.com", "password": "pass", "role": "viewer",
            "organization_id": org_id,
        })
        assert r.status_code == 403

    async def test_second_user_wrong_org_admin(self, client, db):
        # Org A: full bootstrap
        r = await client.post("/api/v1/organizations/", json={"name": "Org A2", "slug": "org-a2"})
        org_a = r.json()["id"]
        r = await client.post("/api/v1/users/", json={
            "email": "admin-a2@boot.com", "password": "pass", "role": "admin",
            "organization_id": org_a,
        })
        user_a = r.json()["id"]
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_a})
        key_a = r.json()["key"]

        # Org B is seeded directly in DB because API org creation is locked
        # after the first organization is created.
        org_b_obj = await make_organization(db, name="Org B2", slug="org-b2")
        org_b = str(org_b_obj.id)
        await make_user(db, org_b_obj, email="admin-b2@boot.com", role="admin")

        # Org A admin tries to create user in Org B -> 403
        r = await client.post("/api/v1/users/", json={
            "email": "crossorg@boot.com", "password": "pass", "role": "viewer",
            "organization_id": org_b,
        }, headers={"X-API-Key": key_a})
        assert r.status_code == 403

    async def test_bootstrap_key_two_users_rejected(self, client):
        """Bootstrap fails when org already has >1 user."""
        r = await client.post("/api/v1/organizations/", json={"name": "Org C", "slug": "org-c-2users"})
        org_id = r.json()["id"]

        # First user + bootstrap key
        r = await client.post("/api/v1/users/", json={
            "email": "admin-c@boot.com", "password": "pass", "role": "admin",
            "organization_id": org_id,
        })
        user_id = r.json()["id"]
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_id})
        key = r.json()["key"]

        # Second user via admin
        r = await client.post("/api/v1/users/", json={
            "email": "user2-c@boot.com", "password": "pass", "role": "viewer",
            "organization_id": org_id,
        }, headers={"X-API-Key": key})
        assert r.status_code == 200
        user2_id = r.json()["id"]

        # Bootstrap for user2 fails — org has 2 users
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user2_id})
        assert r.status_code == 403
        assert "exactly one user" in r.json()["detail"]

    async def test_bootstrap_key_user_has_key_rejected(self, client):
        """Second bootstrap call fails because user already has a key."""
        r = await client.post("/api/v1/organizations/", json={"name": "Org D", "slug": "org-d-haskey"})
        org_id = r.json()["id"]
        r = await client.post("/api/v1/users/", json={
            "email": "admin-d@boot.com", "password": "pass", "role": "admin",
            "organization_id": org_id,
        })
        user_id = r.json()["id"]

        # First bootstrap succeeds
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_id})
        assert r.status_code == 200

        # Second bootstrap fails — user already has a key
        r = await client.post("/api/v1/auth/keys/bootstrap", json={"user_id": user_id})
        assert r.status_code == 403
        assert "no existing API keys" in r.json()["detail"]
