"""Read-only database connection verifier."""

from __future__ import annotations

import sys

from sqlalchemy import text

from app.core.config.settings import settings
from app.core.database.sanitization import sanitize_database_error
from app.core.database.session import dispose_engine, get_engine


def main() -> int:
    print("DATABASE CONNECTION CHECK")
    try:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured. Add it to backend/.env.")
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Status: CONNECTED")
        print("Database connection established successfully.")
        return 0
    except Exception as exc:
        print("Status: NOT CONNECTED")
        print(f"Error: {sanitize_database_error(exc)}")
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    sys.exit(main())
