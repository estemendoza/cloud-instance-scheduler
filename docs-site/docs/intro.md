---
sidebar_position: 1
slug: /
---

# Cloud Instance Scheduler

Cloud Instance Scheduler (CIS) lets you define schedules for your AWS, Azure, and GCP instances. It handles start/stop automation, tracks every action, and gives you a clear view of your savings. No agents to install, no code changes — just connect your cloud accounts and set your policies.

## Key capabilities

- **Multi-cloud** — manage AWS, Azure, and GCP instances from a single dashboard
- **Flexible schedules** — visual weekly grid or cron expressions with timezone support
- **Auto start/stop** — reconciliation engine continuously enforces desired state
- **Overrides** — temporary per-resource overrides with automatic expiration
- **Cost savings** — savings tracking and a what-if cost calculator
- **Audit trail** — full execution history and state transition log
- **Self-hosted** — runs on your own infrastructure

## Documentation map

- [Getting started](./getting-started.md): setup, bootstrap, and first login
- [Connecting cloud accounts](./cloud-providers.md): provider setup with IAM guides for AWS, Azure, and GCP
- [Scheduling](./scheduling.md): policies, weekly grid, cron expressions, and reconciliation
- [Overrides](./overrides.md): temporary state overrides and precedence rules
- [Executions](./executions.md): audit trail and execution history
- [Cost calculator](./pricing-and-savings.md): savings tracking and what-if cost estimates
- [Deployment](./deployment.md): production configuration, authentication, and roles
- [Testing](./testing.md): test suite and development setup
- [Contributing a provider](./contributing-provider.md): how to add support for a new cloud provider

## Core workflow

1. Create the first organization and admin user.
2. Add one or more cloud accounts.
3. Discover resources from the configured providers.
4. Define schedules using the weekly grid or cron expressions.
5. Apply temporary overrides when needed.
6. Let reconciliation enforce desired state and review execution history.

## API reference

The backend exposes OpenAPI documentation at `/api/v1/docs` in a running environment. Keep the product docs focused on concepts and operations, and use the OpenAPI reference for endpoint-level contracts.
