---
sidebar_position: 8
---

# Deployment

CIS is a three-part application: a PostgreSQL database, a FastAPI backend, and a Svelte frontend. The included `docker-compose.yml` bundles all three, so the simplest deployment is a single machine running Docker Compose.

This page covers what you need to know for a production deployment.

## Secrets

Set strong, unique values for these environment variables before going live:

| Variable | Purpose |
|---|---|
| `ENCRYPTION_KEY` | Encrypts cloud credentials at rest in the database |
| `JWT_SECRET_KEY` | Signs authentication tokens — if compromised, all sessions are invalid |
| `POSTGRES_PASSWORD` | Database password |

You can generate secure keys with:

```bash
openssl rand -hex 32
```

Never reuse keys across environments. If you rotate `ENCRYPTION_KEY`, existing cloud account credentials will need to be re-entered.

## Authentication

CIS supports two authentication methods:

### Browser sessions (JWT)

Users log in with email and password. The backend issues a short-lived access token and a longer-lived refresh token. The frontend handles token refresh automatically — users stay logged in across page reloads.

### API keys

For programmatic access (scripts, CI/CD, external integrations), create an API key from **Settings > API Keys**. Send it in the request header:

```
X-API-Key: your-api-key-here
```

API keys are stored hashed — CIS never stores the raw key after creation. Copy it when it's first displayed.

When both a JWT and an API key are present, JWT takes precedence.

## Roles

Users have one of three roles:

| Role | What they can do |
|---|---|
| **Admin** | Everything — manage users, cloud accounts, policies, overrides, API keys, and organization settings |
| **Operator** | Create and manage policies, overrides, and view all resources and executions |
| **Viewer** | Read-only access to resources, executions, and the dashboard |

The first user created during bootstrap is always an admin.

## Scheduler and reconciliation

The reconciliation scheduler runs in-process with the backend. It periodically checks each resource's desired state (based on policies and overrides) against its actual state in the cloud, and issues start or stop commands to resolve any differences.

**Single-replica constraint:** In a multi-replica deployment, each replica runs its own scheduler, which means duplicate start/stop commands. If you need multiple backend replicas, you'll need to add leader election or a distributed lock (e.g., using PostgreSQL advisory locks) to ensure only one replica runs the scheduler.

## Networking

- The frontend and backend can run on separate hosts — configure `PUBLIC_API_URL` in the frontend environment to point to the backend
- Review CORS settings before exposing the API publicly. Set `CORS_ALLOW_ALL_ORIGINS=false` and configure specific allowed origins for production
- The backend serves the API on port 8000 and the frontend on port 3000 by default

## Database migrations

Apply Alembic migrations before switching traffic to a new release:

```bash
alembic upgrade head
```

Or with Docker Compose:

```bash
docker compose exec app alembic upgrade head
```

Migrations are forward-only. Always back up your database before applying migrations in production.

## Rollout checklist

1. Provision PostgreSQL (or use the bundled container)
2. Set all required environment variables (secrets, database, CORS)
3. Deploy the backend and frontend containers
4. Run database migrations
5. Verify the API is healthy: `GET /api/v1/system/status`
6. On first install, complete the bootstrap wizard to create your organization and admin user
