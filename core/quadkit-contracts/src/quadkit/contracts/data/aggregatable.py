from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AggregatableProtocol(Protocol):
    """Protocol for data aggregation."""

    async def aggregate(
        self,
        group_by: list[str],
        aggregations: dict[str, str],
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


__all__ = ["AggregatableProtocol"]
