from tests.conftest import make_policy, make_cloud_account, make_resource

_VALID_SCHEDULE = {
    "monday": [{"start": "09:00", "end": "17:00"}],
    "tuesday": [{"start": "09:00", "end": "17:00"}],
}

_VALID_POLICY = {
    "name": "Test Policy",
    "timezone": "UTC",
    "schedule": _VALID_SCHEDULE,
    "resource_selector": {"tags": {"env": "test"}},
}


class TestPolicies:
    async def test_create_admin(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/policies/", json=_VALID_POLICY, headers=headers)
        assert r.status_code == 201
        assert r.json()["name"] == "Test Policy"

    async def test_create_viewer_rejected(self, client, viewer_headers):
        r = await client.post("/api/v1/policies/", json=_VALID_POLICY, headers=viewer_headers)
        assert r.status_code == 403

    async def test_create_invalid_schedule(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/policies/", json={
            **_VALID_POLICY,
            "schedule": {"monday": [{"start": "18:00", "end": "09:00"}]},
        }, headers=headers)
        assert r.status_code == 422

    async def test_create_invalid_timezone(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/policies/", json={
            **_VALID_POLICY,
            "timezone": "Not/A/Real/Zone",
        }, headers=headers)
        assert r.status_code == 422

    async def test_create_selector_both_tags_and_ids(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/policies/", json={
            **_VALID_POLICY,
            "resource_selector": {"tags": {"a": "b"}, "resource_ids": ["x"]},
        }, headers=headers)
        assert r.status_code == 422

    async def test_create_selector_neither_tags_nor_ids(self, client, org_and_admin):
        _, _, headers = org_and_admin
        r = await client.post("/api/v1/policies/", json={
            **_VALID_POLICY,
            "resource_selector": {},
        }, headers=headers)
        assert r.status_code == 422

    async def test_list(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        await make_policy(db, org, name="Alpha")
        await make_policy(db, org, name="Beta")

        r = await client.get("/api/v1/policies/", headers=headers)
        assert r.status_code == 200
        names = [p["name"] for p in r.json()]
        assert "Alpha" in names
        assert "Beta" in names

    async def test_update(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        policy = await make_policy(db, org, name="Before")

        r = await client.put(f"/api/v1/policies/{policy.id}",
                             json={"name": "After"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "After"

    async def test_delete(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        policy = await make_policy(db, org)

        r = await client.delete(f"/api/v1/policies/{policy.id}", headers=headers)
        assert r.status_code == 204

        r = await client.get(f"/api/v1/policies/{policy.id}", headers=headers)
        assert r.status_code == 404

    async def test_preview_by_tags(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        # 3 resources with matching tag
        for _ in range(3):
            await make_resource(db, org, ca, tags={"env": "test"})
        # 1 resource without matching tag
        await make_resource(db, org, ca, tags={"env": "prod"})

        policy = await make_policy(db, org, resource_selector={"tags": {"env": "test"}})
        r = await client.get(f"/api/v1/policies/{policy.id}/preview", headers=headers)
        assert r.status_code == 200
        assert r.json()["affected_resource_count"] == 3

    async def test_preview_by_resource_ids(self, client, db, org_and_admin):
        org, _, headers = org_and_admin
        ca = await make_cloud_account(db, org)
        resource = await make_resource(db, org, ca)

        policy = await make_policy(db, org, resource_selector={"resource_ids": [str(resource.id)]})
        r = await client.get(f"/api/v1/policies/{policy.id}/preview", headers=headers)
        assert r.status_code == 200
        assert r.json()["affected_resource_count"] == 1
