import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db():
    """AsyncMock that stands in for an AsyncSession."""
    return AsyncMock(spec=AsyncSession)


def make_result(scalar=None, scalars=None):
    """Return a mock DB result object compatible with the common access patterns."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalar_one.return_value = scalar
    result.scalar.return_value = scalar  # for func.count() queries
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars if scalars is not None else []
    result.scalars.return_value = scalars_mock
    return result
