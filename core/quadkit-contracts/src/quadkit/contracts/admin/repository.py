"""AdminRepositoryProtocol — generic admin CRUD repository."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class AdminRepositoryProtocol(Protocol[T]):
    """Protocol for admin repository operations."""

    async def find_many(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: list[tuple[str, str]] | None = None,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        search_fields: list[str] | None = None,
        load: list[str] | None = None,
    ) -> list[T]: ...

    async def find_by_id(self, item_id: Any) -> T | None: ...

    async def count(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        search_fields: list[str] | None = None,
    ) -> int: ...

    async def create(self, data: dict[str, Any]) -> T: ...

    async def update(self, item_id: Any, data: dict[str, Any]) -> T: ...

    async def delete(self, item_id: Any) -> bool: ...


__all__ = ["AdminRepositoryProtocol"]
