"""Shared authenticated request context."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RequestContext:
    """Validated authorization context for a protected request."""

    authenticated_auth_user_id: UUID
    app_user_id: UUID
    assignment_id: UUID
    tenant_id: UUID | None
    branch_id: UUID | None
    canonical_role_codes: frozenset[str]
    permission_keys: frozenset[str]
    enabled_modules: frozenset[str]
    scope_type: str
    correlation_id: str | None = None

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permission_keys

    def has_any_permission(self, permission_keys: set[str] | frozenset[str]) -> bool:
        return bool(self.permission_keys.intersection(permission_keys))

    def has_module(self, module_code: str) -> bool:
        return module_code in self.enabled_modules
