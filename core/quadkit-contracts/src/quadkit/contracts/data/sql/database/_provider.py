"""Database provider protocol."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

from quadkit.contracts.core import HealthCheckResult
from quadkit.contracts.data.sql.database._connection import ConnectionProtocol
from quadkit.contracts.data.sql.database._pool import ConnectionPoolProtocol
from quadkit.contracts.data.sql.database._results import (
    DeleteResult,
    InsertResult,
    IsolationLevel,
    QueryResult,
    UpdateResult,
)


class DatabaseProviderProtocol(Protocol):
    """Protocol for database providers.

    This defines the interface that all database providers must implement,
    regardless of the underlying database technology.

    Example:
        ```python
        class PostgresProvider:
            async def connect(self) -> None:
                self._pool = await asyncpg.create_pool(self._dsn)

            async def execute_query(
                self,
                sql: str,
                params: list[Any] | None = None,
            ) -> QueryResult:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(sql, *params or [])
                    return QueryResult(rows=list(map(dict, rows)), ...)
        ```
    """

    # Connection lifecycle
    async def connect(self) -> None:
        """Establish connection to the database."""
        ...

    async def disconnect(self) -> None:
        """Close connection to the database."""
        ...

    async def is_connected(self) -> bool:
        """Check if database is connected."""
        ...

    async def get_primary_pool(self) -> ConnectionPoolProtocol:
        """Return the primary connection pool.

        For multi-backend setups, returns the backend marked `primary: true`.
        Raises NoPrimaryBackendError if no primary is marked or zero backends.

        Returns:
            The primary connection pool.

        Raises:
            NoPrimaryBackendError: If no primary backend is configured.
        """
        ...

    # Query execution
    async def execute_query(
        self,
        sql: str,
        params: list[Any] | None = None,
        **kwargs: Any,
    ) -> QueryResult:
        """Execute a SELECT query.

        Args:
            sql: SQL query string.
            params: Query parameters.
            **kwargs: Additional options.

        Returns:
            QueryResult with rows and execution metadata.
        """
        ...

    async def execute_insert(
        self,
        table: str,
        data: dict[str, Any],
        **kwargs: Any,
    ) -> InsertResult:
        """Execute an INSERT operation.

        Args:
            table: Table name.
            data: Column-value mapping.
            **kwargs: Additional options.

        Returns:
            InsertResult with inserted ID and influenced rows.
        """
        ...

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        where_clause: str,
        where_params: list[Any] | None = None,
        **kwargs: Any,
    ) -> UpdateResult:
        """Execute an UPDATE operation.

        Args:
            table: Table name.
            data: Column-value updates.
            where_clause: WHERE condition.
            where_params: Parameters for WHERE clause.
            **kwargs: Additional options.

        Returns:
            UpdateResult with affected rows.
        """
        ...

    async def execute_delete(
        self,
        table: str,
        where_clause: str,
        where_params: list[Any] | None = None,
        **kwargs: Any,
    ) -> DeleteResult:
        """Execute a DELETE operation.

        Args:
            table: Table name.
            where_clause: WHERE condition.
            where_params: Parameters for WHERE clause.
            **kwargs: Additional options.

        Returns:
            DeleteResult with affected rows.
        """
        ...

    async def execute(
        self,
        sql: str,
        params: Any = None,
    ) -> QueryResult:
        """Execute a raw SQL query with parameters.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            QueryResult with execution results.
        """
        ...

    # Transaction management
    def transaction(
        self, isolation_level: IsolationLevel | None = None
    ) -> AbstractAsyncContextManager[Any]:
        """Context manager for transactions.

        Args:
            isolation_level: Optional ANSI SQL isolation level.  When ``None``
                the driver's default isolation level is used.

        Example:
            ```python
            async with db.transaction(isolation_level=IsolationLevel.SERIALIZABLE):
                await db.execute("INSERT INTO ...")
                await db.execute("UPDATE ...")
            ```
        """
        ...

    async def begin_transaction(self) -> None:
        """Begin a transaction."""
        ...

    async def commit_transaction(self) -> None:
        """Commit current transaction."""
        ...

    async def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        ...

    # Schema operations
    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        ...

    # Health check
    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check on database connection."""
        ...

    # Scoped session management
    def scoped_context(self) -> AbstractAsyncContextManager[Any]:
        """Return an async context manager that establishes a scoped session.

        The scoped context binds a database session to the current
        async context so that ``get_scoped_connection`` can retrieve it
        without passing the connection around explicitly.

        Returns:
            Async context manager that yields no value (or the session).
        """
        ...

    async def get_scoped_connection(self) -> ConnectionProtocol:
        """Return the connection bound to the current scoped context.

        Must be called within an active :meth:`scoped_context` block.

        Returns:
            Active :class:`ConnectionProtocol` for the current scope.
        """
        ...

    # Connection pool acquisition (low-level)
    async def acquire(self) -> ConnectionProtocol:
        """Acquire a connection from the pool for manual management.

        Use this when you need fine-grained control over connection lifecycle,
        but prefer :meth:`scoped_context` when possible for automatic cleanup.

        Returns:
            An acquired connection that must be released via :meth:`release`.

        Example:
            ```python
            conn = await db.acquire()
            try:
                result = await conn.execute("SELECT * FROM users")
            finally:
                await db.release(conn)
            ```
        """
        ...

    async def release(self, connection: ConnectionProtocol) -> None:
        """Release a connection back to the pool.

        Args:
            connection: Connection acquired via :meth:`acquire`.
        """
        ...
