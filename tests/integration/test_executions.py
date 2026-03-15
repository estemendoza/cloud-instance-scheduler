from datetime import datetime, timedelta, timezone

from tests.conftest import make_cloud_account, make_resource, make_execution


class TestExecutions:
    async def test_list_no_filter(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        await make_execution(db, org, resource, action="STOP")
        await make_execution(db, org, resource, action="START")

        r = await client.get("/api/v1/executions/", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_filter_by_action(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        await make_execution(db, org, resource, action="STOP")
        await make_execution(db, org, resource, action="START")

        r = await client.get("/api/v1/executions/?action=START", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["action"] == "START"

    async def test_filter_by_success(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        await make_execution(db, org, resource, success=True)
        await make_execution(db, org, resource, success=False)

        r = await client.get("/api/v1/executions/?success=true", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["success"] is True

    async def test_filter_by_hours(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        now = datetime.now(timezone.utc)
        await make_execution(db, org, resource, executed_at=now - timedelta(hours=2))
        await make_execution(db, org, resource, executed_at=now - timedelta(hours=48))

        r = await client.get("/api/v1/executions/?hours=24", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_statistics(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)
        await make_execution(db, org, resource, action="START", success=True)
        await make_execution(db, org, resource, action="STOP", success=True)
        await make_execution(db, org, resource, action="START", success=False)

        r = await client.get("/api/v1/executions/statistics?hours=24", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_executions"] == 3
        assert body["successful"] == 2
        assert body["failed"] == 1
        assert body["actions"]["START"] == 2
        assert body["actions"]["STOP"] == 1

    async def test_reconcile_admin(self, client, org_and_admin):
        """Reconcile with 0 resources returns empty counts."""
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/executions/reconcile", headers=headers)
        assert r.status_code == 200
        assert r.json() == {"processed": 0, "actions_taken": 0, "errors": 0}

    async def test_reconcile_viewer_rejected(self, client, viewer_headers):
        r = await client.post("/api/v1/executions/reconcile", headers=viewer_headers)
        assert r.status_code == 403
