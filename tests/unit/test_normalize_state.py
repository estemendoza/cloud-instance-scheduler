import pytest
from unittest.mock import patch

from app.providers.aws_ec2 import AWSEC2Provider
from app.providers.models import AWSCredentials, InstanceState


@pytest.fixture
def provider():
    creds = AWSCredentials(access_key_id="AKIA_TEST", secret_access_key="secret", region="us-east-1")
    with patch("app.providers.aws_ec2.boto3.client"):
        return AWSEC2Provider(creds)


class TestNormalizeState:
    def test_running(self, provider):
        assert provider._normalize_state("running") == InstanceState.RUNNING

    def test_stopped(self, provider):
        assert provider._normalize_state("stopped") == InstanceState.STOPPED

    def test_pending(self, provider):
        assert provider._normalize_state("pending") == InstanceState.RUNNING

    def test_stopping(self, provider):
        assert provider._normalize_state("stopping") == InstanceState.STOPPED

    def test_shutting_down(self, provider):
        assert provider._normalize_state("shutting-down") == InstanceState.STOPPED

    def test_terminated_is_unknown(self, provider):
        # Regression: must be UNKNOWN, not STOPPED
        assert provider._normalize_state("terminated") == InstanceState.UNKNOWN

    def test_unknown_string(self, provider):
        assert provider._normalize_state("weird-state") == InstanceState.UNKNOWN

    def test_case_insensitive(self, provider):
        assert provider._normalize_state("RUNNING") == InstanceState.RUNNING
