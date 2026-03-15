# CLAUDE.md — Cloud Instance Scheduler (CIS)

## Project Overview

Multi-tenant app that discovers, schedules, and reconciles cloud compute instances (start/stop) across AWS, Azure, and GCP to reduce costs. FastAPI backend + SvelteKit frontend + PostgreSQL.

## Quick Reference

- **Backend**: FastAPI + SQLAlchemy async + asyncpg + Alembic (Python 3.11+)
- **Frontend**: SvelteKit 2 + Svelte 4 + TypeScript + Tailwind 3
- **DB**: PostgreSQL 15 (async via asyncpg)
- **Scheduler**: APScheduler (in-process, 5-min interval)
- **Package manager**: Poetry (backend), npm (frontend)
- **Container runtime**: Podman (not Docker)

## Repository Structure

```
app/
  main.py              # FastAPI entrypoint
  api/v1/              # REST endpoints (policies, resources, executions, etc.)
  api/deps.py          # Auth dependencies (JWT + API key) and RBAC
  core/config.py       # Pydantic settings (reads .env)
  core/jwt.py          # JWT token utilities
  core/security.py     # Password hashing, API key generation
  models/              # SQLAlchemy ORM models
  schemas/             # Pydantic request/response schemas
  services/            # Domain logic (discovery, policy_engine, reconciliation, cost_calculator, etc.)
  providers/           # Cloud provider abstraction (base.py, aws.py, azure_vm.py, gcp.py)
  db/                  # Base model, async session/engine
frontend/src/
  lib/api/client.ts    # Typed fetch wrapper with Bearer auth
  lib/stores/auth.ts   # Auth state (JWT in memory, refresh in localStorage)
  routes/              # SvelteKit pages (/, /resources, /policies, /settings, /calculator, etc.)
alembic/               # DB migrations
tests/                 # unit/, services/, providers/, integration/
```

## Development Commands

### Backend
```bash
# Start dev services (DB + backend + frontend)
podman-compose up -d

# Run backend only
uvicorn app.main:app --reload

# Run all tests (auto-starts test DB via podman if needed)
poetry run pytest

# Run specific test suite
poetry run pytest tests/unit/
poetry run pytest tests/services/
poetry run pytest tests/integration/
poetry run pytest tests/providers/

# Lint
poetry run flake8 app/

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Frontend
```bash
cd frontend
npm run dev          # Dev server on :3000
npm run build        # Production build
npm run check        # Svelte/TS type checking
npm run lint         # ESLint
```

## Testing

- Tests use a **separate Postgres** instance on port 7777 (via `docker-compose.test.yml`)
- The test DB auto-starts via Podman if not already running (disable with `CIS_TEST_DB_AUTOSTART=0`)
- `pytest-asyncio` with `asyncio_mode = "auto"` — async test functions just work
- Test fixtures in `tests/conftest.py`: `db`, `client`, `app`, plus factory helpers (`make_organization`, `make_user`, `make_resource`, `make_policy`, etc.)
- Coverage is configured: `--cov=app --cov-report=term-missing`

## Key Architecture Decisions

- **Auth**: Dual auth — JWT (browser) + API keys (programmatic). JWT checked first, falls back to API key. See `app/api/deps.py`.
- **Multi-tenancy**: All data is org-scoped. Organization is the top-level tenant.
- **Policy engine**: Desired state precedence: active override > matching policy schedule > default STOPPED.
- **Reconciliation**: Compares desired vs actual state, creates pending Execution before calling cloud API, updates to completed/failed after.
- **Credentials**: Encrypted at rest with Fernet (`ENCRYPTION_KEY` env var). Never logged or returned in API responses.
- **Provider abstraction**: `app/providers/base.py` defines the interface. New providers implement `validate_credentials`, `list_instances`, `get_instance_state`, `start_instance`, `stop_instance`.

## Environment Variables

Required in `.env`:
- `ENCRYPTION_KEY` — Fernet key for credential encryption
- `JWT_SECRET_KEY` — HMAC key for JWT signing (32+ chars)
- `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`

Optional:
- `CORS_ALLOW_ALL_ORIGINS` — set `True` in production behind reverse proxy
- `PRICING_UPDATE_HOUR_UTC` / `PRICING_UPDATE_MINUTE_UTC` — daily pricing fetch time

## Conventions

- Backend follows standard FastAPI patterns: routers in `api/v1/endpoints/`, Pydantic schemas for validation, SQLAlchemy models with async sessions.
- Frontend uses SvelteKit file-based routing, Tailwind for styling, Tabler icons.
- API prefix: `/api/v1`
- All timestamps in UTC.
- Alembic migrations should be generated with `--autogenerate` and reviewed before applying.

## Browser Testing (agent-browser)

`agent-browser` is installed globally and can be used to visually verify UI changes:

```bash
# Open a page
npx agent-browser open http://localhost:3000

# Take a screenshot (use Read tool to view it)
npx agent-browser screenshot /tmp/screenshot.png

# Get accessibility tree with element refs
npx agent-browser snapshot

# Interact with elements (use refs from snapshot)
npx agent-browser fill <ref> '<value>'
npx agent-browser click <ref>

# Run JS in the page
npx agent-browser eval "document.title"

# Close browser
npx agent-browser close
```

Login flow: fill email (ref from snapshot), fill password, click Sign In. Or set auth via JS:
```bash
npx agent-browser eval "fetch('http://localhost:8000/api/v1/auth/token', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:'...', password:'...'})}).then(r=>r.json()).then(d=>{localStorage.setItem('refreshToken',d.refresh_token); document.title='OK'}); 'pending'"
```
Then navigate to the target page.

## Related Docs

- [architecture.md](architecture.md) — detailed architecture snapshot (data model, request flows, provider details)
- [INNOVATION.md](INNOVATION.md) — AI advisory integration design and use cases
