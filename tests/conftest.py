import asyncio as _asyncio
import os
import shutil
import socket
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import bcrypt as _bcrypt
import pytest

# Use minimum bcrypt rounds in tests — same code paths, ~30x faster hashing.
# Default rounds=12 adds ~0.3-0.5s per hash; rounds=4 is the minimum allowed.
_real_gensalt = _bcrypt.gensalt
_bcrypt.gensalt = lambda rounds=4, prefix=b'2b': _real_gensalt(rounds=4, prefix=prefix)
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 — registers all ORM classes with Base.metadata
from app.core.security import generate_api_key, get_api_key_hash, get_password_hash
from app.db.base import Base
from app.db.session import get_db

TEST_DB_HOST = os.getenv("POSTGRES_SERVER", "localhost")
TEST_DB_PORT = int(os.getenv("POSTGRES_PORT", "7777"))
_test_user = os.getenv("POSTGRES_USER", "postgres")
_test_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
_test_db = os.getenv("POSTGRES_DB", "cis_test")
TEST_DATABASE_URL = f"postgresql+asyncpg://{_test_user}:{_test_pass}@{TEST_DB_HOST}:{TEST_DB_PORT}/{_test_db}"
TEST_COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker-compose.test.yml"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)


def _is_test_db_reachable(timeout: float = 0.5) -> bool:
    """Check whether the test Postgres port is reachable."""
    try:
        with socket.create_connection((TEST_DB_HOST, TEST_DB_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def _get_podman_compose_cmd() -> list[str]:
    """
    Resolve the Podman compose command.

    Preference:
    1) podman-compose
    2) podman compose
    """
    if shutil.which("podman-compose"):
        return ["podman-compose"]

    if shutil.which("podman"):
        probe = subprocess.run(
            ["podman", "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode == 0:
            return ["podman", "compose"]

    raise RuntimeError(
        "Test DB is not reachable and no Podman compose command was found. "
        "Install `podman-compose` or enable `podman compose`."
    )


def _wait_for_test_db(timeout_seconds: int = 60) -> None:
    """Wait until Postgres accepts SQL connections."""
    _asyncio.run(_wait_for_db_ready_async(timeout_seconds))


async def _wait_for_db_ready_async(timeout_seconds: int = 60) -> None:
    """Wait until `SELECT 1` succeeds against the test DB."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _is_test_db_reachable():
            await _asyncio.sleep(1)
            continue

        probe_engine = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            poolclass=NullPool,
        )
        try:
            async with probe_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception:
            await _asyncio.sleep(1)
        finally:
            await probe_engine.dispose()

    raise RuntimeError(
        f"Timed out waiting for test DB at {TEST_DB_HOST}:{TEST_DB_PORT}"
    )


@pytest.fixture(scope="session")
def ensure_test_db():
    """
    Ensure the integration test DB exists.

    If Postgres is already running, reuse it.
    Otherwise, auto-start via Podman Compose and tear it down when done.
    Set CIS_TEST_DB_AUTOSTART=0 to disable auto-start behavior.
    """
    autostart_enabled = os.getenv("CIS_TEST_DB_AUTOSTART", "1") not in {"0", "false", "False"}

    if _is_test_db_reachable():
        yield
        return

    if not autostart_enabled:
        raise RuntimeError(
            "Test DB is not reachable and auto-start is disabled "
            "(set CIS_TEST_DB_AUTOSTART=1 or start it manually)."
        )

    compose_cmd = _get_podman_compose_cmd()
    subprocess.run(
        compose_cmd + ["-f", str(TEST_COMPOSE_FILE), "up", "-d"],
        check=True,
    )

    try:
        _wait_for_test_db()
        yield
    finally:
        subprocess.run(
            compose_cmd + ["-f", str(TEST_COMPOSE_FILE), "down"],
            check=False,
        )


# ─── Table lifecycle ──────────────────────────────────────────────────────────


async def _create_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session")
def setup_tables(ensure_test_db):
    """Create all tables once at session start (sync fixture, uses asyncio.run)."""
    _asyncio.run(_create_tables())
    yield


# ─── Core fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def db(setup_tables):
    """Per-test database session. Commits are real; cleanup happens via the
    integration conftest's autouse truncation fixture."""
    async with AsyncSession(_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture(scope="session")
def app():  # noqa: F811
    """FastAPI app with APScheduler startup/shutdown neutralized."""
    from app.main import app as _app

    _app.router.on_startup.clear()
    _app.router.on_shutdown.clear()
    return _app


@pytest.fixture(autouse=True)
def _reset_rate_limiter(app):
    """Clear the rate limiter storage between tests to avoid cross-test 429s."""
    from app.core.rate_limit import limiter
    if hasattr(limiter, "_limiter") and hasattr(limiter._limiter, "_storage"):
        limiter._limiter._storage.reset()
    elif hasattr(limiter, "_storage"):
        limiter._storage.reset()
    yield


@pytest.fixture
async def client(app, db):
    """Async HTTP client with get_db overridden to use the test engine."""

    async def _override_get_db():
        async with AsyncSession(_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ─── Entity factories ─────────────────────────────────────────────────────────
# Plain async helpers — call with `await` inside tests or other fixtures.


async def make_organization(db, name="Test Org", slug=None):
    from app.models.user import Organization

    if slug is None:
        slug = name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:8]
    org = Organization(name=name, slug=slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def make_user(db, org, email=None, role="viewer", password="testpass123"):
    from app.models.user import User

    if email is None:
        email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name="Test User",
        role=role,
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_api_key(db, user):
    from app.models.apikey import APIKey

    raw_key = generate_api_key()
    key_hash = get_api_key_hash(raw_key)
    prefix = raw_key[:8]
    db_key = APIKey(
        key_hash=key_hash,
        prefix=prefix,
        name="test-key",
        user_id=user.id,
        expires_at=None,
    )
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)
    return raw_key, db_key


async def make_cloud_account(db, org, name="Test AWS", provider_type="aws",
                             encrypted_creds=None):
    from app.models.cloud_account import CloudAccount

    if encrypted_creds is None:
        encrypted_creds = "dummy-encrypted-creds"
    account = CloudAccount(
        organization_id=org.id,
        name=name,
        provider_type=provider_type,
        credentials_encrypted=encrypted_creds,
        is_active=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def make_resource(db, org, cloud_account, state="RUNNING", tags=None,
                        instance_type="t3.micro", region="us-east-1",
                        provider_resource_id=None):
    from app.models.resource import Resource

    if provider_resource_id is None:
        provider_resource_id = f"i-{uuid.uuid4().hex[:17]}"
    if tags is None:
        tags = {}
    resource = Resource(
        organization_id=org.id,
        cloud_account_id=cloud_account.id,
        provider_resource_id=provider_resource_id,
        name=f"test-instance-{uuid.uuid4().hex[:6]}",
        region=region,
        resource_type="instance",
        state=state,
        tags=tags,
        instance_type=instance_type,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


async def make_policy(db, org, name="Test Policy", schedule=None,
                      resource_selector=None):
    from app.models.policy import Policy

    if schedule is None:
        schedule = {
            day: [{"start": "09:00", "end": "17:00"}]
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
        }
    if resource_selector is None:
        resource_selector = {"tags": {"env": "test"}}
    policy = Policy(
        organization_id=org.id,
        name=name,
        timezone="UTC",
        schedule=schedule,
        resource_selector=resource_selector,
        is_enabled=True,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def make_override(db, org, resource, desired_state="RUNNING",
                        expires_at=None, user=None):
    from app.models.override import Override

    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    if user is None:
        user = await make_user(db, org, role="admin")
    override = Override(
        organization_id=org.id,
        resource_id=resource.id,
        desired_state=desired_state,
        expires_at=expires_at,
        reason="test override",
        created_by_user_id=user.id,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return override


async def make_execution(db, org, resource, action="STOP", success=True,
                         executed_at=None):
    from app.models.execution import Execution

    if executed_at is None:
        executed_at = datetime.now(timezone.utc)
    execution = Execution(
        organization_id=org.id,
        resource_id=resource.id,
        action=action,
        desired_state="STOPPED" if action == "STOP" else "RUNNING",
        actual_state_before="RUNNING" if action == "STOP" else "STOPPED",
        success=success,
        error_message=None if success else "test error",
        executed_at=executed_at,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


async def make_pricing(db, provider_type="aws", region="us-east-1",
                       instance_type="t3.micro", hourly_rate=None):
    from app.models.pricing import InstancePricing

    if hourly_rate is None:
        hourly_rate = Decimal("0.1")
    pricing = InstancePricing(
        provider_type=provider_type,
        region=region,
        instance_type=instance_type,
        hourly_rate=hourly_rate,
    )
    db.add(pricing)
    await db.commit()
    await db.refresh(pricing)
    return pricing
