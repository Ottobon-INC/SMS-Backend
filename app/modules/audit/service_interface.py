"""Audit service interface for future high-impact operations.

This task intentionally does not write audit rows. Future modules should depend
on this boundary instead of writing ad hoc audit logic inside routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuditCommand:
    tenant_id: UUID | None
    branch_id: UUID | None
    actor_user_id: UUID
    action: str
    target_type: str
    target_id: UUID | None
    outcome: str
    reason: str | None = None
    correlation_id: str | None = None


class AuditServiceInterface:
    """Deferred audit boundary; real persistence will be added with audit LLD."""

    def record(self, command: AuditCommand) -> None:
        raise NotImplementedError("Audit persistence is not implemented in this foundation task.")
