"""Tests for database-level CASCADE delete behaviour.

Verifies that deleting a cloud account cascades to resources, executions,
overrides, and resource state events. Also verifies that deleting a user
sets created_by_user_id to NULL on overrides (SET NULL behaviour).
"""

from sqlalchemy import select, func

from app.models.resource import Resource
from app.models.execution import Execution
from app.models.override import Override
from app.models.resource_state_event import ResourceStateEvent
from tests.conftest import (
    make_user, make_cloud_account, make_resource,
    make_execution, make_override,
)


async def _make_state_event(db, org, resource, prev="STOPPED", new="RUNNING"):
    event = ResourceStateEvent(
        organization_id=org.id,
        resource_id=resource.id,
        previous_state=prev,
        new_state=new,
        source="discovery",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


class TestCloudAccountCascadeDelete:
    """Deleting a cloud account should cascade-delete all child records."""

    async def test_resources_deleted(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org)
        await make_resource(db, org, account)
        await make_resource(db, org, account)

        r = await client.delete(
            f"/api/v1/cloud-accounts/{account.id}", headers=headers)
        assert r.status_code == 204

        count = await db.scalar(
            select(func.count(Resource.id)).where(
                Resource.cloud_account_id == account.id))
        assert count == 0

    async def test_executions_deleted(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org)
        resource = await make_resource(db, org, account)
        await make_execution(db, org, resource, action="STOP")
        await make_execution(db, org, resource, action="START")

        await client.delete(
            f"/api/v1/cloud-accounts/{account.id}", headers=headers)

        count = await db.scalar(
            select(func.count(Execution.id)).where(
                Execution.resource_id == resource.id))
        assert count == 0

    async def test_overrides_deleted(self, client, db, org_and_admin):
        org, admin, headers = org_and_admin
        account = await make_cloud_account(db, org)
        resource = await make_resource(db, org, account)
        await make_override(db, org, resource, user=admin)

        await client.delete(
            f"/api/v1/cloud-accounts/{account.id}", headers=headers)

        count = await db.scalar(
            select(func.count(Override.id)).where(
                Override.resource_id == resource.id))
        assert count == 0

    async def test_state_events_deleted(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        account = await make_cloud_account(db, org)
        resource = await make_resource(db, org, account)
        await _make_state_event(db, org, resource)

        await client.delete(
            f"/api/v1/cloud-accounts/{account.id}", headers=headers)

        count = await db.scalar(
            select(func.count(ResourceStateEvent.id)).where(
                ResourceStateEvent.resource_id == resource.id))
        assert count == 0

    async def test_other_accounts_unaffected(self, client, db, org_and_admin):
        """Deleting one account should not touch another account's resources."""
        org, _, headers = org_and_admin
        account_a = await make_cloud_account(db, org, name="Account A")
        account_b = await make_cloud_account(db, org, name="Account B")
        await make_resource(db, org, account_a)
        await make_resource(db, org, account_b)

        await client.delete(
            f"/api/v1/cloud-accounts/{account_a.id}", headers=headers)

        count = await db.scalar(
            select(func.count(Resource.id)).where(
                Resource.cloud_account_id == account_b.id))
        assert count == 1


class TestUserDeleteSetNull:
    """Deleting a user should SET NULL on override.created_by_user_id."""

    async def test_override_creator_set_null_on_user_delete(
        self, client, db, org_and_admin
    ):
        org, admin, headers = org_and_admin
        account = await make_cloud_account(db, org)
        resource = await make_resource(db, org, account)

        # Create a second admin who will be deleted
        other_admin = await make_user(db, org, role="admin")
        override = await make_override(db, org, resource, user=other_admin)
        override_id = override.id

        # Delete the user who created the override
        r = await client.delete(
            f"/api/v1/users/{other_admin.id}", headers=headers)
        assert r.status_code == 204

        # Override should still exist, but created_by_user_id should be NULL
        db.expire_all()
        result = await db.execute(
            select(Override).where(Override.id == override_id))
        override = result.scalar_one()
        assert override is not None
        assert override.created_by_user_id is None
