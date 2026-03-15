---
sidebar_position: 2
---

# Getting Started

## Prerequisites

- Docker or Podman
- Docker Compose (or Podman Compose)

That's it for running CIS. For local development without containers, see [Local development](#local-development-without-docker) below.

## Quick start with pre-built images

The fastest way to get CIS running. Pre-built images are available on Docker Hub — no need to clone the repo or build anything.

### Images

| Image | Description |
|-------|-------------|
| `estemendoza/cis:api-latest` | Backend API (FastAPI + Uvicorn) |
| `estemendoza/cis:frontend-latest` | Frontend (SvelteKit + nginx) |

Versioned tags are also available: `estemendoza/cis:api-1.0.0`, `estemendoza/cis:frontend-1.0.0`.

### Deploy

1. Download the deployment compose file and environment template:

```bash
curl -O https://raw.githubusercontent.com/estemendoza/cis/main/docker-compose.deploy.yml
curl -O https://raw.githubusercontent.com/estemendoza/cis/main/.env.production.example
cp .env.production.example .env
```

2. Edit `.env` with your production values. Generate secure keys:

```bash
# Encryption key for cloud credentials (Fernet)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# JWT signing key
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Database password
POSTGRES_PASSWORD=$(openssl rand -hex 16)
```

3. Start services:

```bash
podman-compose -f docker-compose.deploy.yml up -d
```

4. Run database migrations:

```bash
podman-compose -f docker-compose.deploy.yml run --rm app alembic upgrade head
```

5. Open the application:

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **API**: [http://localhost:8000](http://localhost:8000)

### Architecture

The deployment runs three containers:

- **frontend** (nginx) — serves the pre-built SvelteKit app and proxies `/api` requests to the backend
- **app** (uvicorn) — FastAPI backend, runs the scheduler in-process
- **db** (postgres:15-alpine) — PostgreSQL database with a persistent volume

### Updating

```bash
# Pull new images
podman-compose -f docker-compose.deploy.yml pull

# Run migrations with the new image
podman-compose -f docker-compose.deploy.yml run --rm app alembic upgrade head

# Restart services
podman-compose -f docker-compose.deploy.yml up -d

# Clean up old images
podman image prune -f
```

## Bootstrap

On first launch, the app shows a bootstrap wizard to create the initial organization and admin user.

The bootstrap sequence:

1. **Create organization** — give your org a name
2. **Create admin user** — set email, name, and password
3. **Authenticate** — the app logs you in automatically

After bootstrap, the login screen is shown for returning users:

![Login screen](/img/screenshots/login.png)

## Onboarding

Once authenticated, the dashboard shows a guided onboarding flow with four steps to get you up and running:

![Dashboard onboarding](/img/screenshots/dashboard-onboarding.png)

The steps are:

1. **Connect a cloud account** (AWS, Azure, or GCP)
2. **Sync and discover your instances**
3. **Create policies to schedule start/stop**
4. **Watch the savings add up**

Click the **Connect Cloud Account** button to get started.

### Step 1: Add a cloud account

Navigate to **Settings > Cloud Accounts** and click **+ Add Account**. If you have no accounts yet, the page shows an empty state prompting you to add your first one:

![Settings — empty cloud accounts](/img/screenshots/settings-cloud-accounts.png)

Select your cloud provider and enter the required credentials. Each provider requires different fields:

#### AWS

Provide your IAM Access Key ID and Secret Access Key. You can scope access with a read-only IAM policy or allow start/stop actions. See [AWS setup instructions](cloud-providers#aws) for how to create an IAM user and policy.

![Add AWS account](/img/screenshots/add-account-aws.png)

#### Azure

Provide your Subscription ID, Tenant ID, Client ID (App ID), and Client Secret. Create a service principal in Azure AD with the `Virtual Machine Contributor` role. See [Azure setup instructions](cloud-providers#azure) for the full walkthrough.

![Add Azure account](/img/screenshots/add-account-azure.png)

#### GCP

Provide your Project ID and a Service Account JSON key. The service account needs `compute.instances.list`, `compute.instances.start`, and `compute.instances.stop` permissions. See [GCP setup instructions](cloud-providers#gcp) for how to create a service account and download the key.

![Add GCP account](/img/screenshots/add-account-gcp.png)

For all providers, you can choose to scan **all regions** or **select specific regions** to limit discovery scope. You can also toggle whether the account is active.

Click **Add Account** to save. The app will validate your credentials and begin discovering instances. For more details on credential requirements and permissions, see the [Connecting Cloud Accounts](cloud-providers) page.

### Step 2: Discover resources

After adding a cloud account, CIS automatically syncs and discovers your compute instances. You can view them on the **Resources** page:

![Resources page](/img/screenshots/resources.png)

Use the filters at the top to narrow by provider, state, or region. Each resource shows its name, current state (running/stopped), region, instance type, and when it was last seen.

### Step 3: Create a policy

Navigate to **Policies** and click **Create Policy** to define scheduling rules for your instances:

![Policies page](/img/screenshots/policies.png)

Policies define operating windows for your instances. You can use the **weekly grid** to visually paint hours, or switch to **cron expressions** for more flexible schedules.

**Weekly grid** — click and drag to select running hours per day:

![Weekly schedule grid](/img/screenshots/policy-schedule-grid.png)

**Cron expressions** — define start and stop times with standard cron syntax:

![Cron expression schedule](/img/screenshots/policy-cron.png)

### Step 4: Monitor savings

Once policies are active and the scheduler is running, the **Dashboard** will show KPI cards with estimated monthly savings, resource counts, execution success rates, and recent failures. You can also use the **Calculator** page for detailed per-resource cost projections.

![Active dashboard](/img/screenshots/dashboard.png)

## Local development with Podman Compose

The dev compose stack runs the full application (DB + backend + frontend) with hot reload enabled on both the backend and frontend.

### Setup

1. Clone the repo and create your environment file:

```bash
git clone https://github.com/estemendoza/cis.git
cd cis
cp .env.example .env
```

2. Edit `.env` with your local values. At minimum set:

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET_KEY=$(openssl rand -hex 32)
```

3. Start the stack:

```bash
podman-compose up -d
```

4. Apply database migrations:

```bash
podman-compose exec app alembic upgrade head
```

5. Open the application:

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **API**: [http://localhost:8000](http://localhost:8000)
- **OpenAPI docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

### Hot reload

Both services watch for file changes automatically:

- **Backend** — the `app/` directory is mounted into the container. Uvicorn runs with `--reload`, so any Python file change restarts the server instantly. File system polling is enabled via `WATCHFILES_FORCE_POLLING=true` for compatibility with Podman's virtual filesystem.
- **Frontend** — `frontend/src/` and `frontend/static/` are mounted. Vite's HMR updates the browser without a full reload. Polling is enabled via `CHOKIDAR_USEPOLLING=true`.

### Useful commands

```bash
# View logs
podman-compose logs -f app
podman-compose logs -f frontend

# Restart a single service after a dependency change
podman-compose restart app

# Rebuild after changing pyproject.toml or package.json
podman-compose up --build -d

# Stop the stack
podman-compose down
```

## Local development without Docker

For contributors or developers who want to run outside containers. Requires Python 3.11+, Poetry 2.x, Node.js 20+, and PostgreSQL 15+.

### Backend

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

## Configuration

Key environment variables (see `.env.production.example` for the full list):

| Variable | Description |
|---|---|
| `POSTGRES_SERVER` | Database host |
| `POSTGRES_PORT` | Database port |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |
| `ENCRYPTION_KEY` | Encryption key for cloud credentials |
| `JWT_SECRET_KEY` | Secret for JWT token signing |
| `PRICING_UPDATE_HOUR_UTC` | Hour (UTC) for automatic pricing refresh |
| `PRICING_UPDATE_MINUTE_UTC` | Minute for automatic pricing refresh |
| `CORS_ALLOW_ALL_ORIGINS` | Allow all CORS origins (use with care) |
