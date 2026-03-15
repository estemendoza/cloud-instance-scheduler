import uuid

from tests.conftest import make_cloud_account, make_resource


class TestResources:
    async def test_list_no_filter(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        await make_resource(db, org, ca)
        await make_resource(db, org, ca)

        r = await client.get("/api/v1/resources/", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["total_pages"] == 1

    async def test_filter_by_state(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        await make_resource(db, org, ca, state="RUNNING")
        await make_resource(db, org, ca, state="STOPPED")

        r = await client.get(
            "/api/v1/resources/?state=RUNNING", headers=headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["state"] == "RUNNING"

    async def test_filter_by_region(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        await make_resource(db, org, ca, region="us-east-1")
        await make_resource(db, org, ca, region="eu-west-1")

        r = await client.get(
            "/api/v1/resources/?region=eu-west-1", headers=headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["region"] == "eu-west-1"

    async def test_filter_by_cloud_account_id(
        self, client, db, org_and_admin
    ):
        org, _, headers = org_and_admin
        ca1 = await make_cloud_account(db, org, name="CA1")
        ca2 = await make_cloud_account(db, org, name="CA2")
        await make_resource(db, org, ca1)
        await make_resource(db, org, ca2)

        r = await client.get(
            f"/api/v1/resources/?cloud_account_id={ca1.id}",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["cloud_account_id"] == str(ca1.id)

    async def test_filter_by_provider_type(
        self, client, db, org_and_admin
    ):
        org, _, headers = org_and_admin
        aws_ca = await make_cloud_account(
            db, org, name="AWS CA", provider_type="aws"
        )
        await make_resource(db, org, aws_ca)

        r = await client.get(
            "/api/v1/resources/?provider_type=aws",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1

    async def test_pagination(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        for i in range(5):
            await make_resource(db, org, ca)

        # Page 1 with page_size=2
        r = await client.get(
            "/api/v1/resources/?page=1&page_size=2",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

        # Page 3 with page_size=2 (should have 1 item)
        r = await client.get(
            "/api/v1/resources/?page=3&page_size=2",
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["page"] == 3

    async def test_get_by_id(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(
            db, org, ca, tags={"env": "test"}
        )

        r = await client.get(
            f"/api/v1/resources/{resource.id}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(resource.id)
        assert r.json()["tags"] == {"env": "test"}

    async def test_get_not_found(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.get(
            f"/api/v1/resources/{uuid.uuid4()}",
            headers=headers,
        )
        assert r.status_code == 404
