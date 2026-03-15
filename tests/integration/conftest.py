import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from tests.conftest import make_organization, make_user, make_api_key


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    """Ensure a valid Fernet key is available for encrypt/decrypt calls."""
    monkeypatch.setattr(
        "app.core.config.settings.ENCRYPTION_KEY",
        Fernet.generate_key().decode(),
    )


@pytest.fixture(autouse=True)
async def cleanup(db):
    """Truncate all tables after each integration test using the shared db session."""
    yield
    import app.models  # noqa — registers all ORM models with Base.metadata
    from app.db.base import Base

    await db.rollback()
    table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await db.execute(text(f"TRUNCATE {table_names} CASCADE"))
    await db.commit()


@pytest.fixture
async def org_and_admin(db):
    """Seed org + admin user + API key. Returns (org, admin_user, headers)."""
    org = await make_organization(db)
    admin = await make_user(db, org, role="admin")
    raw_key, _ = await make_api_key(db, admin)
    return org, admin, {"X-API-Key": raw_key}


@pytest.fixture
async def operator_headers(db, org_and_admin):
    """Seed an operator in the same org; return its auth headers."""
    org, _, _ = org_and_admin
    operator = await make_user(db, org, role="operator")
    raw_key, _ = await make_api_key(db, operator)
    return {"X-API-Key": raw_key}


@pytest.fixture
async def viewer_headers(db, org_and_admin):
    """Seed a viewer in the same org; return its auth headers."""
    org, _, _ = org_and_admin
    viewer = await make_user(db, org, role="viewer")
    raw_key, _ = await make_api_key(db, viewer)
    return {"X-API-Key": raw_key}
