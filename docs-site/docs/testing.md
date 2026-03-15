---
sidebar_position: 9
---

# Testing

This section is for developers contributing to CIS.

## Test structure

The repository includes several test layers:

- `tests/unit` — isolated unit tests
- `tests/services` — service-layer tests
- `tests/providers` — cloud provider adapter tests
- `tests/integration` — end-to-end tests against a real database

## Running tests

Run all tests with pytest:

```bash
poetry run pytest
```

Coverage and JUnit artifacts are generated automatically:

- `coverage.xml`
- `pytest-results.xml`

## Integration database

Integration tests use a PostgreSQL database (`cis_test`) on `localhost:7777`.

The test harness can auto-start this database using `docker-compose.test.yml` with Podman when the database isn't already reachable. To disable auto-start:

```bash
CIS_TEST_DB_AUTOSTART=0 poetry run pytest
```

## Provider tests

If you're adding a new cloud provider, see [Contributing a Provider](./contributing-provider.md) for the full guide including test patterns and minimum coverage requirements.
