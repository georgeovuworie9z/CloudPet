# CloudPet Backend

FastAPI + PostgreSQL backend for CloudPet. This document covers local development
only; AWS infrastructure and deployment are handled separately.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker + Docker Compose (optional, for running the full local stack)

## Setup

```bash
cd backend
uv sync
```

Copy the example environment file and adjust values:

```bash
cp ../.env.example ../.env
```

Required environment variables:

| Variable                          | Description                                   |
| --------------------------------- | --------------------------------------------- |
| `ENVIRONMENT`                     | `local` \| `test` \| `staging` \| `production` |
| `DATABASE_URL`                    | SQLAlchemy/psycopg PostgreSQL URL             |
| `JWT_SECRET_KEY`                  | HS256 signing key (used by a later milestone) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes (default 30) |

## Running

Full stack (API + PostgreSQL) via Docker Compose, from the repository root:

```bash
docker compose up --build
```

API only, against a PostgreSQL you provide via `DATABASE_URL`:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

- Health check: `GET http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

## Checks

```bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy app tests
uv run pytest
```

## Database migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"
```
