import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.analytics import AnalyticsService
from tests.services.conftest import make_result


def _execution(action="STOP", success=True):
    return SimpleNamespace(
        action=action,
        success=success,
        executed_at=datetime.now(timezone.utc),
    )


class TestGetExecutionStatistics:
    def _service(self, mock_db):
        return AnalyticsService(db=mock_db)

    async def test_empty(self, mock_db):
        svc = self._service(mock_db)
        mock_db.execute = AsyncMock(return_value=make_result(scalars=[]))
        result = await svc.get_execution_statistics(uuid.uuid4(), hours=24)
        assert result == {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
            "actions": {"START": 0, "STOP": 0},
            "period_hours": 24,
        }

    async def test_mixed(self, mock_db):
        svc = self._service(mock_db)
        execs = [
            _execution("START", True),
            _execution("START", True),
            _execution("STOP", True),
            _execution("START", False),
        ]
        mock_db.execute = AsyncMock(return_value=make_result(scalars=execs))
        result = await svc.get_execution_statistics(uuid.uuid4(), hours=24)
        assert result["total_executions"] == 4
        assert result["successful"] == 3
        assert result["failed"] == 1
        assert result["success_rate"] == 0.75
        assert result["actions"] == {"START": 3, "STOP": 1}

    async def test_all_failures(self, mock_db):
        svc = self._service(mock_db)
        execs = [_execution(success=False) for _ in range(3)]
        mock_db.execute = AsyncMock(return_value=make_result(scalars=execs))
        result = await svc.get_execution_statistics(uuid.uuid4(), hours=24)
        assert result["success_rate"] == 0.0
        assert result["failed"] == 3
