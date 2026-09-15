"""Admin operation protocols — bulk, search, aggregation, transaction, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.lifecycle import (
    AuditableProtocol,
    CacheAwareProtocol,
    ExportableProtocol,
    TransactionalProtocol,
    ValidatableProtocol,
)

if TYPE_CHECKING:
    from quadkit.contracts.data import QueryResult


@runtime_checkable
class BulkOperationsProtocol(Protocol):
    """Bulk CRUD operations on admin data sources."""

    async def bulk_create(self, records: list[dict[str, Any]]) -> list[Any]: ...

    async def bulk_update(
        self, updates: list[dict[str, Any]], filters: dict[str, Any] | None = None
    ) -> int: ...

    async def bulk_delete(self, filters: dict[str, Any]) -> int: ...


@runtime_checkable
class RelationLoaderProtocol(Protocol):
    """Loads related records for admin list/detail views."""

    async def load_relations(
        self, records: list[dict[str, Any]], relations: list[str]
    ) -> list[dict[str, Any]]: ...

    async def get_relation_options(
        self, relation_name: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class AdminSearchableProtocol(Protocol):
    """Full-text search against admin data sources."""

    async def search(
        self,
        query: str,
        fields: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> QueryResult: ...


@runtime_checkable
class AggregatableProtocol(Protocol):
    """Data aggregation for admin dashboards and reports."""

    async def aggregate(
        self,
        group_by: list[str],
        aggregations: dict[str, str],
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


__all__ = [
    "AdminSearchableProtocol",
    "AggregatableProtocol",
    "AuditableProtocol",
    "BulkOperationsProtocol",
    "CacheAwareProtocol",
    "ExportableProtocol",
    "RelationLoaderProtocol",
    "TransactionalProtocol",
    "ValidatableProtocol",
]
