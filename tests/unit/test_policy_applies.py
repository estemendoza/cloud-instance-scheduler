import uuid
from types import SimpleNamespace

from app.services.policy_engine import PolicyEngine


def _policy(selector):
    return SimpleNamespace(resource_selector=selector)


def _resource(id=None, tags=None):
    return SimpleNamespace(id=id or uuid.uuid4(), tags=tags)


# _policy_applies_to_resource is a regular method but only reads
# policy.resource_selector and resource.{id,tags} — db is never touched.
_engine = PolicyEngine(db=None)


class TestPolicyAppliesById:
    def test_match(self):
        rid = uuid.uuid4()
        assert _engine._policy_applies_to_resource(
            _policy({"resource_ids": [str(rid)]}),
            _resource(id=rid),
        ) is True

    def test_no_match(self):
        assert _engine._policy_applies_to_resource(
            _policy({"resource_ids": [str(uuid.uuid4())]}),
            _resource(id=uuid.uuid4()),
        ) is False


class TestPolicyAppliesByTags:
    def test_all_tags_match(self):
        policy = _policy({"tags": {"env": "prod", "team": "be"}})
        resource = _resource(tags={"env": "prod", "team": "be", "extra": "ignored"})
        assert _engine._policy_applies_to_resource(policy, resource) is True

    def test_one_tag_missing(self):
        policy = _policy({"tags": {"env": "prod", "team": "be"}})
        resource = _resource(tags={"env": "prod"})
        assert _engine._policy_applies_to_resource(policy, resource) is False

    def test_resource_tags_none(self):
        policy = _policy({"tags": {"env": "prod"}})
        resource = _resource(tags=None)
        assert _engine._policy_applies_to_resource(policy, resource) is False


class TestPolicyAppliesInvalidSelector:
    def test_no_tags_no_ids(self):
        policy = _policy({"cloud_account_id": "some-id"})
        resource = _resource(tags={"env": "prod"})
        assert _engine._policy_applies_to_resource(policy, resource) is False
