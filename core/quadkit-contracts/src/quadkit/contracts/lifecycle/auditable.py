from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditableProtocol(Protocol):
    """Protocol for audit logging."""

    async def log_operation(
        self,
        operation: str,
        record_id: Any,
        changes: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None: ...

    async def get_audit_log(
        self,
        record_id: Any | None = None,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...


__all__ = ["AuditableProtocol"]
