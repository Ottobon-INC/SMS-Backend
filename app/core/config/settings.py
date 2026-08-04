from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


def _clean_database_url(value: str) -> str:
    """Normalize common .env paste shapes without exposing credentials."""

    cleaned = value.strip()
    if cleaned.upper().startswith("DATABASE_URL="):
        cleaned = cleaned.split("=", 1)[1].strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _prepare_sqlalchemy_database_url(value: str) -> URL:
    """Return a SQLAlchemy PostgreSQL URL compatible with the configured DBAPI."""

    url: URL = make_url(value)
    if "pgbouncer" in url.query:
        query = dict(url.query)
        query.pop("pgbouncer", None)
        url = url.set(query=query)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername == "postgres":
        url = url.set(drivername="postgresql+psycopg")
    return url


class Settings(BaseSettings):
    app_name: str = "Student Management System Backend"
    app_env: str = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str = ""
    supabase_url: str = "http://localhost:54321"
    redis_url: str = "redis://localhost:6379/0"
    sentry_dsn: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def normalized_database_url(self) -> str:
        """Return a SQLAlchemy psycopg URL without exposing or mutating the raw env value."""

        database_url = _clean_database_url(self.database_url)
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured. Add it to backend/.env.")

        url = _prepare_sqlalchemy_database_url(database_url)
        return url.render_as_string(hide_password=False)

    def safe_database_identity(self) -> str:
        """Return a sanitized database identity for logs."""

        database_url = _clean_database_url(self.database_url)
        if not database_url:
            return "not configured"
        url = make_url(database_url)
        host = url.host or "unknown"
        port = url.port or "default"
        database = url.database or ""
        return f"{url.drivername}://{host}:{port}/{database}"


settings = Settings()
