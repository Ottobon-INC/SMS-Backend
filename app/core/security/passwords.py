"""Password hashing helpers for backend-owned authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.core.config.settings import settings

PASSWORD_ALGORITHM = "PBKDF2_SHA256"


def normalize_login_identifier(value: str) -> str:
    """Normalize username/email identifiers for credential lookup."""

    return value.strip().lower()


def generate_password_salt() -> str:
    """Generate a URL-safe salt for password hashing."""

    return base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("ascii")


def hash_password(
    password: str,
    *,
    salt: str,
    iterations: int | None = None,
    pepper: str | None = None,
) -> str:
    """Return a PBKDF2-HMAC-SHA256 password hash encoded for storage."""

    configured_iterations = iterations or settings.password_hash_iterations
    configured_pepper = settings.password_pepper if pepper is None else pepper
    material = f"{password}{configured_pepper}".encode()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        material,
        salt.encode("utf-8"),
        configured_iterations,
    )
    return base64.urlsafe_b64encode(digest).decode("ascii")


def verify_password(
    password: str,
    *,
    expected_hash: str,
    salt: str,
    iterations: int,
    pepper: str | None = None,
) -> bool:
    """Compare a submitted password to a stored hash without leaking timing."""

    candidate = hash_password(password, salt=salt, iterations=iterations, pepper=pepper)
    return hmac.compare_digest(candidate, expected_hash)
