import pytest
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from app.providers.models import InstanceState


def _client_error(code, operation="DescribeInstances"):
    return ClientError(
        {"Error": {"Code": code, "Message": "mock"}},
        operation,
    )


class TestValidateCredentials:
    def test_validate_success(self, aws_provider, mock_boto3_client):
        mock_boto3_client.get_caller_identity.return_value = {
            "Account": "123456789012"
        }
        result = aws_provider.validate_credentials()
        assert result.is_valid is True
        assert result.error_message is None

    def test_validate_client_error(self, aws_provider, mock_boto3_client):
        mock_boto3_client.get_caller_identity.side_effect = _client_error(
            "InvalidClientTokenId", "GetCallerIdentity"
        )
        result = aws_provider.validate_credentials()
        assert result.is_valid is False
        assert "InvalidClientTokenId" in result.error_message

    def test_validate_generic_error(self, aws_provider, mock_boto3_client):
        mock_boto3_client.get_caller_identity.side_effect = Exception(
            "network down"
        )
        result = aws_provider.validate_credentials()
        assert result.is_valid is False
        assert "network down" in result.error_message


class TestListInstances:
    def _page(self, instances):
        return {"Reservations": [{"Instances": instances}]}

    def _instance_dict(self, instance_id="i-123", state="running",
                       tags=None, instance_type="t3.micro"):
        d = {
            "InstanceId": instance_id,
            "State": {"Name": state},
            "InstanceType": instance_type,
        }
        if tags is not None:
            d["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
        return d

    def test_list_single_region(self, aws_provider, mock_boto3_client):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            self._page([self._instance_dict("i-1")]),
            self._page([self._instance_dict("i-2")]),
        ]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances(regions=["us-east-1"])
        assert len(result) == 2
        assert result[0].id == "i-1"
        assert result[1].id == "i-2"
        assert result[0].region == "us-east-1"
        assert result[0].provider == "aws"

    def test_list_extracts_name_tag(self, aws_provider, mock_boto3_client):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            self._page([self._instance_dict(
                "i-1", tags={"Name": "web-1", "env": "prod"}
            )])
        ]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances(regions=["us-east-1"])
        assert result[0].name == "web-1"
        assert result[0].tags == {"Name": "web-1", "env": "prod"}

    def test_list_no_name_tag(self, aws_provider, mock_boto3_client):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            self._page([self._instance_dict(
                "i-1", tags={"env": "prod"}
            )])
        ]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances(regions=["us-east-1"])
        assert result[0].name is None

    def test_list_no_tags_key(self, aws_provider, mock_boto3_client):
        """Instance dict has no 'Tags' key at all."""
        paginator = MagicMock()
        inst = {
            "InstanceId": "i-1",
            "State": {"Name": "running"},
            "InstanceType": "t3.micro",
        }
        paginator.paginate.return_value = [self._page([inst])]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances(regions=["us-east-1"])
        assert result[0].tags == {}
        assert result[0].name is None

    def test_list_all_regions(self, aws_provider, mock_boto3_client):
        """No regions arg -> describe_regions first, then paginate per region."""
        mock_boto3_client.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "eu-west-1"},
            ]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [
            self._page([self._instance_dict("i-east")])
        ]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances()
        assert len(result) == 2
        regions = {r.region for r in result}
        assert regions == {"us-east-1", "eu-west-1"}


class TestStartInstance:
    def test_start_success(self, aws_provider, mock_boto3_client):
        mock_boto3_client.start_instances.return_value = {}
        assert aws_provider.start_instance("i-123", "us-east-1") is True
        mock_boto3_client.start_instances.assert_called_once_with(
            InstanceIds=["i-123"]
        )

    def test_start_incorrect_state_idempotent(
        self, aws_provider, mock_boto3_client
    ):
        """IncorrectInstanceState -> True (already running)."""
        mock_boto3_client.start_instances.side_effect = _client_error(
            "IncorrectInstanceState", "StartInstances"
        )
        assert aws_provider.start_instance("i-123", "us-east-1") is True

    def test_start_other_error_raises(
        self, aws_provider, mock_boto3_client
    ):
        """Non-idempotent errors are re-raised."""
        mock_boto3_client.start_instances.side_effect = _client_error(
            "InvalidInstanceID.NotFound", "StartInstances"
        )
        with pytest.raises(ClientError):
            aws_provider.start_instance("i-123", "us-east-1")


class TestStopInstance:
    def test_stop_success(self, aws_provider, mock_boto3_client):
        mock_boto3_client.stop_instances.return_value = {}
        assert aws_provider.stop_instance("i-123", "us-east-1") is True
        mock_boto3_client.stop_instances.assert_called_once_with(
            InstanceIds=["i-123"]
        )

    def test_stop_incorrect_state_idempotent(
        self, aws_provider, mock_boto3_client
    ):
        mock_boto3_client.stop_instances.side_effect = _client_error(
            "IncorrectInstanceState", "StopInstances"
        )
        assert aws_provider.stop_instance("i-123", "us-east-1") is True

    def test_stop_other_error_raises(
        self, aws_provider, mock_boto3_client
    ):
        """Non-idempotent errors are re-raised."""
        mock_boto3_client.stop_instances.side_effect = _client_error(
            "InvalidInstanceID.NotFound", "StopInstances"
        )
        with pytest.raises(ClientError):
            aws_provider.stop_instance("i-123", "us-east-1")


class TestGetInstanceState:
    def test_get_state_running(self, aws_provider, mock_boto3_client):
        mock_boto3_client.describe_instances.return_value = {
            "Reservations": [
                {"Instances": [{"State": {"Name": "running"}}]}
            ]
        }
        assert aws_provider.get_instance_state(
            "i-123", "us-east-1"
        ) == InstanceState.RUNNING

    def test_get_state_empty_reservations(
        self, aws_provider, mock_boto3_client
    ):
        mock_boto3_client.describe_instances.return_value = {
            "Reservations": []
        }
        assert aws_provider.get_instance_state(
            "i-123", "us-east-1"
        ) == InstanceState.UNKNOWN

    def test_get_state_client_error(
        self, aws_provider, mock_boto3_client
    ):
        mock_boto3_client.describe_instances.side_effect = _client_error(
            "InvalidInstanceID.NotFound"
        )
        assert aws_provider.get_instance_state(
            "i-123", "us-east-1"
        ) == InstanceState.UNKNOWN

    def test_get_state_generic_error(
        self, aws_provider, mock_boto3_client
    ):
        """Non-ClientError exceptions return UNKNOWN."""
        mock_boto3_client.describe_instances.side_effect = Exception("boom")
        assert aws_provider.get_instance_state(
            "i-123", "us-east-1"
        ) == InstanceState.UNKNOWN


class TestNormalizeState:
    @pytest.mark.parametrize("ec2_state,expected", [
        ("running", InstanceState.RUNNING),
        ("pending", InstanceState.RUNNING),
        ("stopped", InstanceState.STOPPED),
        ("stopping", InstanceState.STOPPED),
        ("shutting-down", InstanceState.STOPPED),
        ("terminated", InstanceState.UNKNOWN),
        ("something-else", InstanceState.UNKNOWN),
    ])
    def test_normalize(self, aws_provider, ec2_state, expected):
        assert aws_provider._normalize_state(ec2_state) == expected

    def test_normalize_case_insensitive(self, aws_provider):
        assert aws_provider._normalize_state("RUNNING") == InstanceState.RUNNING
        assert aws_provider._normalize_state("Stopped") == InstanceState.STOPPED


class TestListInstancesEdgeCases:
    def _page(self, instances):
        return {"Reservations": [{"Instances": instances}]}

    def test_region_error_continues(self, aws_provider, mock_boto3_client):
        """If one region fails, instances from other regions are returned."""
        call_count = 0

        def _get_paginator_side_effect(op):
            nonlocal call_count
            call_count += 1
            paginator = MagicMock()
            if call_count == 1:
                # First region fails
                paginator.paginate.side_effect = _client_error(
                    "AuthFailure", "DescribeInstances"
                )
            else:
                # Second region succeeds
                paginator.paginate.return_value = [
                    self._page([{
                        "InstanceId": "i-good",
                        "State": {"Name": "running"},
                        "InstanceType": "t3.micro",
                    }])
                ]
            return paginator

        mock_boto3_client.get_paginator.side_effect = (
            _get_paginator_side_effect
        )

        result = aws_provider.list_instances(
            regions=["us-east-1", "eu-west-1"]
        )
        assert len(result) == 1
        assert result[0].id == "i-good"

    def test_empty_reservations(self, aws_provider, mock_boto3_client):
        """Page with no reservations returns empty list."""
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Reservations": []}]
        mock_boto3_client.get_paginator.return_value = paginator

        result = aws_provider.list_instances(regions=["us-east-1"])
        assert result == []

    def test_describe_regions_error_returns_empty(
        self, aws_provider, mock_boto3_client
    ):
        """If describe_regions fails, return empty list."""
        mock_boto3_client.describe_regions.side_effect = Exception("no access")
        result = aws_provider.list_instances()
        assert result == []
