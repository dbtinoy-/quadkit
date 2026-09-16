from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.data import QueryResult


@runtime_checkable
class SearchableProtocol(Protocol):
    """Protocol for searchable admin entities."""

    async def search(
        self,
        query: str,
        fields: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> QueryResult: ...


__all__ = ["SearchableProtocol"]
