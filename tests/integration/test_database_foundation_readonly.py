"""Read-only database integration tests for the manually managed foundation schema."""

import pytest
from sqlalchemy import text

from app.core.config.settings import settings
from app.core.database.sanitization import sanitize_database_error
from app.core.database.session import dispose_engine, get_engine
from app.scripts.verify_schema_sync import compare_schema

pytestmark = pytest.mark.skipif(
    not settings.database_url,
    reason="DATABASE_URL is not configured. Add it to backend/.env.",
)


def test_database_connection_select_one_read_only() -> None:
    try:
        with get_engine().connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    except Exception as exc:
        pytest.fail(sanitize_database_error(exc), pytrace=False)
    finally:
        dispose_engine()


def test_foundation_schema_sync_read_only() -> None:
    try:
        with get_engine().connect() as connection:
            issues = compare_schema(connection)
        assert not issues.has_errors()
    except Exception as exc:
        pytest.fail(sanitize_database_error(exc), pytrace=False)
    finally:
        dispose_engine()
