from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.data import QueryResult


@runtime_checkable
class DataSourceProtocol(Protocol):
    """Protocol for admin data sources with full CRUD support."""

    async def get_data(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult: ...

    async def get_record_count(self, filters: dict[str, Any] | None = None) -> int: ...

    async def create(self, data: dict[str, Any]) -> Any: ...

    async def find_one(self, record_id: Any) -> Any | None: ...

    async def find_many(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]: ...

    async def update(self, record_id: Any, data: dict[str, Any]) -> Any: ...

    async def delete(self, record_id: Any) -> bool: ...

    async def bulk_delete(self, filters: dict[str, Any]) -> int: ...


__all__ = ["DataSourceProtocol"]
