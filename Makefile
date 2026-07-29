SHELL := /bin/sh

.PHONY: install dev test lint format typecheck migrate celery-worker celery-beat

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app tests

migrate:
	uv run alembic upgrade head

celery-worker:
	uv run celery -A celery_app.celery_app worker --loglevel=INFO

celery-beat:
	uv run celery -A celery_app.celery_app beat --loglevel=INFO
