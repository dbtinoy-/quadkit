from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BulkOperationsProtocol(Protocol):
    """Protocol for bulk data operations."""

    async def bulk_create(self, records: list[dict[str, Any]]) -> list[Any]: ...

    async def bulk_update(
        self,
        updates: list[dict[str, Any]],
        filters: dict[str, Any] | None = None,
    ) -> int: ...

    async def bulk_delete(self, filters: dict[str, Any]) -> int: ...


__all__ = ["BulkOperationsProtocol"]
