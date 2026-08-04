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

## Database Configuration

Configure the database URI in `backend/.env`:

```sh
DATABASE_URL=
```

Paste the real Supabase PostgreSQL URI after `DATABASE_URL=` locally. Do not commit or print the real URI.

The backend uses synchronous SQLAlchemy with `psycopg`. If the URI starts with `postgresql://`, the backend normalizes it in memory to `postgresql+psycopg://` without modifying `.env`.

When `DATABASE_URL` is empty, startup and database scripts fail with:

```text
DATABASE_URL is not configured. Add it to backend/.env.
```

## Startup Database Check

FastAPI startup imports the foundation model registry, opens a database connection, executes `SELECT 1`, and logs:

```text
Database connection established successfully.
```

The startup check is read-only. It does not create, alter, drop, insert, update, or delete database objects.

## Read-Only Verification Commands

After pasting the real URI:

```sh
cd backend
.venv/Scripts/python.exe -m app.scripts.verify_database_connection
.venv/Scripts/python.exe -m app.scripts.verify_schema_sync
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

If using a Unix-style virtualenv, replace `.venv/Scripts/python.exe` with the active environment's `python`.

Expected connection success:

```text
DATABASE CONNECTION CHECK
Status: CONNECTED
Database connection established successfully.
```

Expected schema success:

```text
FOUNDATION SCHEMA STATUS: IN SYNC
```

`IN SYNC` means the SQLAlchemy foundation metadata matches the existing `public.sms_*` foundation tables for the checks performed by the verifier. The verifier is read-only and ignores Supabase-managed schemas such as `auth`, `storage`, and `realtime`.

## Database-First Workflow

The live PostgreSQL schema is the source of truth.

For future schema changes:

1. Review and manually apply SQL in the database.
2. Update matching SQLAlchemy models.
3. Run the read-only schema parity verifier.
4. Declare the change complete only when the verifier reports `IN SYNC`.

Do not run schema-changing commands from this backend:

- `Base.metadata.create_all()`
- `Base.metadata.drop_all()`
- `alembic upgrade`
- `alembic downgrade`
- `alembic revision --autogenerate`

Alembic remains present only for metadata comparison support. It must not be used to apply the foundation schema.

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

## Team Ownership

- Pramod owns the foundation model registry and schema-parity process.
- Bhanu and Sampath must use the locked foundation models.
- Module-owned tables may be added later only through reviewed SQL and matching SQLAlchemy models.
- No one may duplicate tenant, user, branch, student, guardian, or enrolment tables.
