"""Database error sanitization helpers."""

from sqlalchemy.engine import make_url

from app.core.config.settings import _clean_database_url, settings


def sanitize_database_error(exc: Exception) -> str:
    """Return an error string that never includes configured connection strings."""

    message = f"{exc.__class__.__name__}: {exc}"
    if settings.database_url:
        message = message.replace(settings.database_url, "[DATABASE_URL_REDACTED]")
        cleaned = _clean_database_url(settings.database_url)
        if cleaned:
            message = message.replace(cleaned, "[DATABASE_URL_REDACTED]")
            try:
                password = make_url(cleaned).password
            except Exception:
                password = None
            if password:
                message = message.replace(password, "[DATABASE_PASSWORD_REDACTED]")
        try:
            normalized = settings.normalized_database_url()
        except Exception:
            normalized = ""
        if normalized:
            message = message.replace(normalized, "[DATABASE_URL_REDACTED]")
    return message
