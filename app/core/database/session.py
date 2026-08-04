"""Synchronous SQLAlchemy database session management."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine, creating it lazily."""

    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.normalized_database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the singleton SQLAlchemy session factory."""

    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that manages a database session lifecycle."""

    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> None:
    """Execute a read-only database connectivity check."""

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("Database connection established successfully.")


def dispose_engine() -> None:
    """Dispose the SQLAlchemy engine during application shutdown."""

    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
