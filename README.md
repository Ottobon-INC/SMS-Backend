# Backend

Single FastAPI modular monolith backend.

Modules under `app/modules/` are internal code boundaries, not microservices. They deploy together as one backend release.

## Commands

```sh
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
uv run ruff check .
uv run mypy app tests
uv run alembic upgrade head
uv run celery -A celery_app.celery_app worker --loglevel=INFO
uv run celery -A celery_app.celery_app beat --loglevel=INFO
```

Health endpoint: `GET /health`

API base: `/api/v1`

## Module Layer Rules

Each backend module owns:

- `models.py` - SQLAlchemy persistence definitions.
- `schemas.py` - Pydantic request and response schemas.
- `repository.py` - scoped database queries; tenant and branch filtering belongs here when persistence is implemented.
- `service.py` - business rules, transactions, workflow coordination, and authorization coordination.
- `router.py` - FastAPI endpoints that call services.
- `permissions.py` - module authorization declarations and helpers.
- `validators.py` - server-side validation helpers that are not Pydantic models.
- `constants.py` - module constants.
- `exceptions.py` - module exceptions.

Frontend schemas = form and UI validation.
Backend schemas = API request and response validation.
Backend models = SQLAlchemy persistence definitions.
Alembic migrations = actual PostgreSQL schema changes.

Alembic migrations live only under `migrations/`. Do not create frontend database schema files or direct frontend database writes.
