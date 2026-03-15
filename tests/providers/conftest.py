import pytest
from unittest.mock import patch, MagicMock

from app.providers.models import AWSCredentials
from app.providers.aws_ec2 import AWSEC2Provider


@pytest.fixture
def mock_boto3_client():
    """Patch boto3.client in the aws_ec2 module; yield the mock client factory.

    The AWS provider creates separate clients per call (EC2, STS),
    so we return the same mock for all boto3.client() calls.
    """
    mock_client = MagicMock()
    with patch(
        "app.providers.aws_ec2.boto3.client",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.fixture
def aws_provider(mock_boto3_client):
    """AWSEC2Provider wired to the mocked boto3 client."""
    creds = AWSCredentials(
        access_key_id="AKIA_TEST",
        secret_access_key="secret",
        region="us-east-1",
    )
    return AWSEC2Provider(creds)
