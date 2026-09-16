from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RelationLoaderProtocol(Protocol):
    """Protocol for loading related data."""

    async def load_relations(
        self,
        records: list[dict[str, Any]],
        relations: list[str],
    ) -> list[dict[str, Any]]: ...

    async def get_relation_options(
        self,
        relation_name: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


__all__ = ["RelationLoaderProtocol"]
