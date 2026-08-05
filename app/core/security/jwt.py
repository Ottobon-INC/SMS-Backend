"""Application JWT creation and verification helpers.

This module intentionally verifies signatures and standard claims. It is used
for FastAPI-owned username/password authentication, not browser-side Supabase
Auth.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.config.settings import settings


class TokenVerificationError(Exception):
    """Raised when a bearer token cannot be trusted."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Verified application principal extracted from an access token."""

    app_user_id: UUID
    claims: dict[str, Any]


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_json_segment(value: str) -> dict[str, Any]:
    try:
        decoded = _decode_base64url(value)
        parsed = json.loads(decoded)
    except Exception as exc:
        raise TokenVerificationError("Invalid token encoding.") from exc
    if not isinstance(parsed, dict):
        raise TokenVerificationError("Invalid token payload.")
    return parsed


def _verify_hs256_signature(signing_input: str, signature: str, secret: str) -> None:
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256)
    expected_signature = base64.urlsafe_b64encode(expected.digest()).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(expected_signature, signature):
        raise TokenVerificationError("Invalid token signature.")


def create_application_access_token(app_user_id: UUID) -> str:
    """Create a signed application access token for a mapped SMS user."""

    if not settings.app_auth_secret:
        raise TokenVerificationError("Application token signing is not configured.")

    now = datetime.now(tz=UTC)
    header = {"alg": "HS256", "typ": "JWT"}
    claims: dict[str, Any] = {
        "sub": str(app_user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "iss": settings.app_auth_issuer,
        "aud": settings.app_auth_audience,
        "typ": "access",
    }
    encoded_header = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    encoded_claims = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signing_input = f"{encoded_header}.{encoded_claims}"
    signature = hmac.new(
        settings.app_auth_secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    )
    encoded_signature = base64.urlsafe_b64encode(signature.digest()).rstrip(b"=").decode("ascii")
    return f"{signing_input}.{encoded_signature}"


def verify_application_access_token(token: str) -> AuthenticatedPrincipal:
    """Validate an application access token and return the authenticated user."""

    if not settings.app_auth_secret:
        raise TokenVerificationError("Application token verification is not configured.")

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenVerificationError("Invalid bearer token.")

    header = _decode_json_segment(parts[0])
    claims = _decode_json_segment(parts[1])
    algorithm = header.get("alg")
    if algorithm != "HS256":
        raise TokenVerificationError("Unsupported token signing algorithm.")

    _verify_hs256_signature(f"{parts[0]}.{parts[1]}", parts[2], settings.app_auth_secret)

    now = int(time.time())
    exp = claims.get("exp")
    if not isinstance(exp, int) or exp <= now:
        raise TokenVerificationError("Token is expired.")

    if settings.app_auth_issuer and claims.get("iss") != settings.app_auth_issuer:
        raise TokenVerificationError("Invalid token issuer.")

    expected_audience = settings.app_auth_audience
    aud = claims.get("aud")
    if expected_audience:
        if isinstance(aud, list):
            valid_audience = expected_audience in aud
        else:
            valid_audience = aud == expected_audience
        if not valid_audience:
            raise TokenVerificationError("Invalid token audience.")

    token_type = claims.get("typ")
    if token_type != "access":
        raise TokenVerificationError("Invalid token type.")

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise TokenVerificationError("Token subject is missing.")
    try:
        app_user_id = UUID(subject)
    except ValueError as exc:
        raise TokenVerificationError("Token subject is not a valid UUID.") from exc

    return AuthenticatedPrincipal(app_user_id=app_user_id, claims=claims)
