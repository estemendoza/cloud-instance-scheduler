import uuid

from tests.conftest import make_organization, make_user, make_api_key


class TestUsersList:
    """Tests for GET /api/v1/users/ endpoint."""

    async def test_admin_can_list_users(self, client, db):
        """Admin can list all users in their organization."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        operator = await make_user(db, org, role="operator")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        users = r.json()
        assert len(users) == 3
        emails = {u["email"] for u in users}
        assert admin.email in emails
        assert operator.email in emails
        assert viewer.email in emails

    async def test_operator_cannot_list_users(self, client, db):
        """Operator cannot list users (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        operator = await make_user(db, org, role="operator")
        raw_key, _ = await make_api_key(db, operator)

        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        assert r.status_code == 403

    async def test_viewer_cannot_list_users(self, client, db):
        """Viewer cannot list users (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, viewer)

        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        assert r.status_code == 403

    async def test_list_users_only_shows_same_org(self, client, db):
        """Admin only sees users from their own organization."""
        org1 = await make_organization(db, name="Org 1")
        org2 = await make_organization(db, name="Org 2")

        admin1 = await make_user(db, org1, role="admin")
        user1 = await make_user(db, org1, role="viewer")
        admin2 = await make_user(db, org2, role="admin")

        raw_key, _ = await make_api_key(db, admin1)

        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        users = r.json()
        emails = {u["email"] for u in users}
        assert admin1.email in emails
        assert user1.email in emails
        assert admin2.email not in emails

    async def test_list_users_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.get("/api/v1/users/")
        assert r.status_code == 401

    async def test_list_users_response_format(self, client, db):
        """Response includes expected fields and organization."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        users = r.json()
        user = users[0]
        assert "id" in user
        assert "email" in user
        assert "full_name" in user
        assert "role" in user
        assert "is_active" in user
        assert "organization_id" in user
        assert "organization" in user
        # Should not include password hash
        assert "hashed_password" not in user
        assert "password" not in user


class TestUsersUpdate:
    """Tests for PUT /api/v1/users/{user_id} endpoint."""

    async def test_admin_can_update_user_role(self, client, db):
        """Admin can change a user's role."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key},
            json={"role": "operator"}
        )
        assert r.status_code == 200
        assert r.json()["role"] == "operator"

    async def test_admin_can_update_user_name(self, client, db):
        """Admin can change a user's full name."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key},
            json={"full_name": "New Name"}
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "New Name"

    async def test_admin_can_deactivate_user(self, client, db):
        """Admin can deactivate a user."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key},
            json={"is_active": False}
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_operator_cannot_update_user(self, client, db):
        """Operator cannot update users (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        operator = await make_user(db, org, role="operator")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, operator)

        r = await client.put(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key},
            json={"role": "operator"}
        )
        assert r.status_code == 403

    async def test_cannot_update_user_in_other_org(self, client, db):
        """Admin cannot update users from another organization."""
        org1 = await make_organization(db, name="Org 1")
        org2 = await make_organization(db, name="Org 2")

        admin1 = await make_user(db, org1, role="admin")
        user2 = await make_user(db, org2, role="viewer")
        raw_key, _ = await make_api_key(db, admin1)

        r = await client.put(
            f"/api/v1/users/{user2.id}",
            headers={"X-API-Key": raw_key},
            json={"role": "operator"}
        )
        assert r.status_code == 404

    async def test_cannot_demote_only_admin(self, client, db):
        """Admin cannot demote themselves if they're the only admin."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/users/{admin.id}",
            headers={"X-API-Key": raw_key},
            json={"role": "viewer"}
        )
        assert r.status_code == 400
        assert "only admin" in r.json()["detail"].lower()

    async def test_can_demote_admin_when_multiple_admins(self, client, db):
        """Admin can demote themselves if there are other admins."""
        org = await make_organization(db)
        admin1 = await make_user(db, org, role="admin")
        await make_user(db, org, role="admin")  # second admin
        raw_key, _ = await make_api_key(db, admin1)

        r = await client.put(
            f"/api/v1/users/{admin1.id}",
            headers={"X-API-Key": raw_key},
            json={"role": "operator"}
        )
        assert r.status_code == 200
        assert r.json()["role"] == "operator"

    async def test_update_nonexistent_user(self, client, db):
        """Updating a nonexistent user returns 404."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.put(
            f"/api/v1/users/{uuid.uuid4()}",
            headers={"X-API-Key": raw_key},
            json={"role": "operator"}
        )
        assert r.status_code == 404

    async def test_update_user_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.put(
            f"/api/v1/users/{uuid.uuid4()}",
            json={"role": "operator"}
        )
        assert r.status_code == 401


class TestUsersDelete:
    """Tests for DELETE /api/v1/users/{user_id} endpoint."""

    async def test_admin_can_delete_user(self, client, db):
        """Admin can delete a user."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.delete(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 204

        # Verify deletion
        r = await client.get("/api/v1/users/", headers={"X-API-Key": raw_key})
        emails = {u["email"] for u in r.json()}
        assert viewer.email not in emails

    async def test_cannot_delete_yourself(self, client, db):
        """Admin cannot delete themselves."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.delete(
            f"/api/v1/users/{admin.id}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 400
        assert "yourself" in r.json()["detail"].lower()

    async def test_operator_cannot_delete_user(self, client, db):
        """Operator cannot delete users (admin only)."""
        org = await make_organization(db)
        await make_user(db, org, role="admin")
        operator = await make_user(db, org, role="operator")
        viewer = await make_user(db, org, role="viewer")
        raw_key, _ = await make_api_key(db, operator)

        r = await client.delete(
            f"/api/v1/users/{viewer.id}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 403

    async def test_cannot_delete_user_in_other_org(self, client, db):
        """Admin cannot delete users from another organization."""
        org1 = await make_organization(db, name="Org 1")
        org2 = await make_organization(db, name="Org 2")

        admin1 = await make_user(db, org1, role="admin")
        user2 = await make_user(db, org2, role="viewer")
        raw_key, _ = await make_api_key(db, admin1)

        r = await client.delete(
            f"/api/v1/users/{user2.id}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 404

    async def test_delete_nonexistent_user(self, client, db):
        """Deleting a nonexistent user returns 404."""
        org = await make_organization(db)
        admin = await make_user(db, org, role="admin")
        raw_key, _ = await make_api_key(db, admin)

        r = await client.delete(
            f"/api/v1/users/{uuid.uuid4()}",
            headers={"X-API-Key": raw_key}
        )
        assert r.status_code == 404

    async def test_delete_user_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        r = await client.delete(f"/api/v1/users/{uuid.uuid4()}")
        assert r.status_code == 401
