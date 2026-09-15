"""Transaction, schema, CRUD, health, and metrics manager protocols."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.core import HealthCheckResult
from quadkit.contracts.data.sql.database._results import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)


class TransactionManagerProtocol(Protocol):
    """Minimal protocol for managing database transactions.

    Consume this instead of :class:`DatabaseProviderProtocol` when you only
    need transaction demarcation (e.g. a Unit of Work decorator).
    """

    async def begin_transaction(self) -> None:
        """Begin a new transaction."""
        ...

    async def commit_transaction(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback_transaction(self) -> None:
        """Roll back the current transaction."""
        ...


@runtime_checkable
class SchemaManagerProtocol(Protocol):
    """Minimal protocol for DDL / schema inspection.

    Consume this instead of :class:`DatabaseProviderProtocol` when you only
    need to inspect or modify the schema (e.g. a migration runner).
    """

    async def table_exists(self, table_name: str) -> bool:
        """Return ``True`` if the named table exists."""
        ...


@runtime_checkable
class CrudOperationsProtocol(Protocol):
    """Minimal protocol for raw CRUD query execution.

    Consume this instead of :class:`DatabaseProviderProtocol` when you only
    need to execute queries and DML statements (e.g. a generic repository).

    All methods return typed result objects so callers do not need to parse
    raw driver-specific return values.
    """

    async def execute_query(
        self,
        query: str,
        params: Any = None,
        *,
        timeout: float | None = None,
    ) -> QueryResult:
        """Execute a SELECT (or any read) query."""
        ...

    async def execute_insert(
        self,
        table: str,
        data: dict[str, Any],
        *,
        returning: list[str] | None = None,
    ) -> InsertResult:
        """Execute an INSERT statement."""
        ...

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        conditions: dict[str, Any],
        *,
        returning: list[str] | None = None,
    ) -> UpdateResult:
        """Execute an UPDATE statement."""
        ...

    async def execute_delete(
        self,
        table: str,
        conditions: dict[str, Any],
    ) -> DeleteResult:
        """Execute a DELETE statement."""
        ...


@runtime_checkable
class HealthMonitorProtocol(Protocol):
    """Minimal protocol for database health checking.

    Consume this instead of :class:`DatabaseProviderProtocol` when you only
    need to probe liveness (e.g. a health endpoint or a readiness probe).
    """

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return the current health of the database connection."""
        ...


@runtime_checkable
class DatabaseMetricsProtocol(Protocol):
    """Minimal protocol for exposing database connection-pool metrics.

    Consume this instead of :class:`DatabaseProviderProtocol` when you only
    need to collect pool telemetry (e.g. a metrics exporter or health dashboard).

    Implementations should return at least the following keys in the dict
    returned by :meth:`get_pool_stats`, though they may include additional
    driver-specific entries:

    * ``active_connections`` – number of connections currently in use.
    * ``idle_connections``   – number of connections available in the pool.
    * ``wait_time_ms``       – average time (ms) callers waited for a connection.
    """

    async def get_pool_stats(self) -> dict[str, int | float]:
        """Return pool statistics keyed by metric name.

        Returns:
            A dict containing at minimum ``active_connections``,
            ``idle_connections``, and ``wait_time_ms`` as ``int`` or
            ``float`` values.
        """
        ...
