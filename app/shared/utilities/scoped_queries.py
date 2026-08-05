"""Scoped query helpers and conventions.

Future module repositories should load protected tenant-owned records by tenant
scope and branch-owned records by tenant plus branch scope. These helpers are
small on purpose; they do not provide an unsafe generic repository abstraction.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select


def require_tenant_filter(statement: Select[Any], table: Any, tenant_id: UUID) -> Select[Any]:
    """Apply the mandatory tenant filter for a tenant-owned table."""

    return statement.where(table.c.tenant_id == tenant_id)


def require_branch_filter(
    statement: Select[Any],
    table: Any,
    *,
    tenant_id: UUID,
    branch_id: UUID,
) -> Select[Any]:
    """Apply mandatory tenant and branch filters for a branch-owned table."""

    return statement.where(table.c.tenant_id == tenant_id, table.c.branch_id == branch_id)
