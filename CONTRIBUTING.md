# Contributing to Cloud Instance Scheduler

Thank you for your interest in contributing to CIS! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15 (or Docker/Podman)
- Poetry (Python package manager)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cis.git
   cd cis
   ```

2. Copy the environment file and configure it:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and generate keys (see comments in file)
   ```

3. Install backend dependencies:
   ```bash
   poetry install
   ```

4. Start the database and apply migrations:
   ```bash
   docker compose up -d db
   alembic upgrade head
   ```

5. Start the backend:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Start the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Running Tests

### Backend

```bash
# Run all tests (starts test DB automatically)
poetry run pytest

# Run specific test suite
poetry run pytest tests/unit/
poetry run pytest tests/services/
poetry run pytest tests/integration/

# Run with coverage
poetry run pytest --cov=app --cov-report=term-missing
```

### Frontend

```bash
cd frontend
npm run check    # Svelte/TypeScript type checking
npm run lint     # ESLint
```

## Code Style

### Python (Backend)

- Follow PEP 8 with a max line length of 88 characters
- Lint with `poetry run flake8 app/`
- Use type hints for function signatures
- Use `logging` instead of `print()` — every module should have `logger = logging.getLogger(__name__)`

### TypeScript/Svelte (Frontend)

- Format with Prettier (`npm run format`)
- Lint with ESLint (`npm run lint`)
- Use TypeScript strict mode

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests and linting to verify everything passes
5. Commit with a clear, descriptive message
6. Push to your fork and open a Pull Request

### Commit Messages

Use clear, imperative-mood commit messages:

- `Add cost calculator feature`
- `Fix JWT refresh token expiration check`
- `Update AWS provider to support new regions`

### Pull Request Guidelines

- Keep PRs focused on a single change
- Include a description of what changed and why
- Ensure CI passes (tests + linting)
- Update documentation if your change affects user-facing behavior

## Project Structure

See the README for an overview of the repository structure and architecture.

## Questions?

Open an issue for bugs or feature requests. For questions about the codebase, check the existing documentation or open a discussion.
