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
