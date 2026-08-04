"""Settings normalization tests."""

from app.core.config.settings import Settings, _clean_database_url


def test_clean_database_url_accepts_plain_url() -> None:
    assert _clean_database_url("postgresql://user:pass@example.test:5432/postgres") == (
        "postgresql://user:pass@example.test:5432/postgres"
    )


def test_clean_database_url_accepts_accidental_nested_assignment() -> None:
    raw_value = 'DATABASE_URL="postgresql://user:pass@example.test:5432/postgres?pgbouncer=true"'
    assert _clean_database_url(raw_value) == (
        "postgresql://user:pass@example.test:5432/postgres?pgbouncer=true"
    )


def test_normalized_database_url_uses_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://user:pass@example.test:5432/postgres")
    assert settings.normalized_database_url().startswith("postgresql+psycopg://")


def test_normalized_database_url_removes_supabase_pooler_marker() -> None:
    settings = Settings(
        database_url="postgresql://user:pass@example.test:5432/postgres?pgbouncer=true&sslmode=require"
    )
    normalized = settings.normalized_database_url()
    assert "pgbouncer" not in normalized
    assert "sslmode=require" in normalized
