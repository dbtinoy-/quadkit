"""AdminAuditLoggerProtocol — admin-specific CRUD audit logging."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.admin.audit_entry import AuditEntry


@runtime_checkable
class AdminAuditLoggerProtocol(Protocol):
    """Protocol for admin-specific CRUD operation audit logging.

    Records individual admin resource operations (create / update / delete)
    with field-level change tracking.
    """

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Any,
        user_id: Any,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    async def write(self, entry: AuditEntry) -> None:
        """Persist a fully-structured audit entry.

        Implementations should delegate to the underlying storage
        (SQL, event store, etc.) and participate in the active unit
        of work when available.
        """
        ...


__all__ = ["AdminAuditLoggerProtocol"]
