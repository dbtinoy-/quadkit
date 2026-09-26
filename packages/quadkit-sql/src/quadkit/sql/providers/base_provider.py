"""
Community edition database providers

These are the basic implementations of the DatabaseProviderProtocol
for the community edition, supporting SQLite, PostgreSQL, and MySQL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, cast

from quadkit.contracts import HealthCheckResult, ProviderPriority
from quadkit.logging import get_logger
from quadkit.sql import (
    ConnectionPoolProtocol,
    DatabaseProviderProtocol,
    DeleteResult,
    InsertResult,
    QueryLoggerProtocol,
    QueryResult,
    UpdateResult,
)
from quadkit.sql.providers.connection_manager import ConnectionManager
from quadkit.sql.providers.crud_operations import CrudOperations
from quadkit.sql.providers.health_monitor import HealthMonitor
from quadkit.sql.providers.query_builder_manager import QueryBuilderManager
from quadkit.sql.providers.query_executor import QueryExecutor
from quadkit.sql.providers.schema_manager import SchemaManager
from quadkit.sql.providers.transaction_manager import TransactionManager

logger = get_logger(__name__)


class DatabaseDriver(DatabaseProviderProtocol, ABC):
    """Database driver base class for all database engines. NOT a DI Provider.

    Subclass for each database engine (Postgres, MySQL, SQLite).
    Handles connections, queries, schema operations, and transactions
    for one database engine. Implements DatabaseProviderProtocol.

    Note:
        Despite the name, this is a driver/engine abstraction, not a DI provider.
        The DI provider wrapper is ``DatabaseService`` in ``database_service.py``
        and the proper DI provider is ``DatabaseProvider`` in ``di_provider.py``.
    """

    name = "database"

    @property
    def database_type(self) -> str:
        """Return the type of database (e.g., 'postgres', 'sqlite')."""
        return self.name

    def __init__(
        self,
        connection_string: str,
        connection_pool: ConnectionPoolProtocol | None = None,
        query_logger: QueryLoggerProtocol | None = None,
        **_kwargs: Any,
    ) -> None:
        # Initialize component managers
        self.connection_manager = self._create_connection_manager(
            connection_string,
            connection_pool,
        )
        # Expose the optional connection pool at provider level for tests/consumers
        self.connection_pool = connection_pool

        self.query_executor = self._create_query_executor(query_logger)
        self.crud_operations = self._create_crud_operations()
        self.transaction_manager = self._create_transaction_manager()
        self.schema_manager = self._create_schema_manager()
        self.query_builder_manager = self._create_query_builder_manager()
        self.health_monitor = self._create_health_monitor()

        # Set up logger
        if hasattr(logger, "bind"):
            self.logger = logger.bind(provider=self.__class__.__name__)
        elif hasattr(logger, "getChild"):
            self.logger = logger.getChild(self.__class__.__name__)
        else:
            self.logger = logger

        # Default priority for database providers
        self._priority = 2  # Normal
        # Repositories cache for model repositories
        self._repositories: dict[type, Any] = {}

    def _create_connection_manager(
        self,
        connection_string: str,
        connection_pool: Any,
    ) -> ConnectionManager:
        """Create the connection manager (to be overridden by subclasses)"""

        # Create a concrete implementation that delegates to this provider
        class ConcreteConnectionManager(ConnectionManager):
            def __init__(
                self,
                provider: Any,
                connection_string: str,
                connection_pool: Any,
            ):
                super().__init__(connection_string, connection_pool)
                self.provider = provider

            async def _create_connection(self) -> Any:
                return await self.provider._create_connection()

            async def _close_connection(self, connection: Any) -> None:
                await self.provider._close_connection(connection)

        return ConcreteConnectionManager(self, connection_string, connection_pool)

    def _create_query_executor(self, query_logger: Any) -> QueryExecutor:
        """Create the query executor (to be overridden by subclasses)"""

        # Create a concrete implementation that delegates to this provider
        class ConcreteQueryExecutor(QueryExecutor):
            def __init__(self, provider: Any, query_logger: Any):
                super().__init__(query_logger)
                self.provider = provider

            async def _execute_query_raw(
                self,
                connection: Any,
                sql: str,
                params: list[Any] | None = None,
            ) -> list[dict[str, Any]]:
                return cast(
                    "list[dict[str, Any]]",
                    await self.provider._execute_query_raw(connection, sql, params),
                )

            async def _execute_modify_raw(
                self,
                connection: Any,
                sql: str,
                params: list[Any] | None = None,
            ) -> int:
                return cast(
                    "int",
                    await self.provider._execute_modify_raw(connection, sql, params),
                )

        return ConcreteQueryExecutor(self, query_logger)

    def _create_crud_operations(self) -> CrudOperations:
        """Create the CRUD operations handler"""

        # Create a concrete implementation that delegates to this provider
        class ConcreteCrudOperations(CrudOperations):
            def __init__(
                self,
                provider: Any,
                query_executor: Any,
                connection_manager: Any,
            ):
                super().__init__(query_executor, connection_manager)
                self.provider = provider

            async def _get_last_insert_id(
                self,
                connection: Any,
                table: str,
            ) -> Any | None:
                return await self.provider._get_last_insert_id(connection, table)

        return ConcreteCrudOperations(
            self,
            self.query_executor,
            self.connection_manager,
        )

    def _create_transaction_manager(self) -> TransactionManager:
        """Create the transaction manager (to be overridden by subclasses)"""

        # Create a concrete implementation that delegates to this provider
        class ConcreteTransactionManager(TransactionManager):
            def __init__(self, provider: Any, connection_manager: Any):
                super().__init__(connection_manager)
                self.provider = provider

            async def _begin_transaction_raw(
                self, connection: Any, isolation: Any | None = None
            ) -> None:
                await self.provider._begin_transaction_raw(connection, isolation)

            async def _commit_transaction_raw(self, connection: Any) -> None:
                await self.provider._commit_transaction_raw(connection)

            async def _rollback_transaction_raw(self, connection: Any) -> None:
                await self.provider._rollback_transaction_raw(connection)

        return ConcreteTransactionManager(self, self.connection_manager)

    def _create_schema_manager(self) -> SchemaManager:
        """Create the schema manager"""
        return SchemaManager(self.crud_operations)  # type: ignore[arg-type]

    def _create_query_builder_manager(self) -> QueryBuilderManager:
        """Create the query builder manager"""
        return QueryBuilderManager(self.crud_operations)

    def _create_health_monitor(self) -> HealthMonitor:
        """Create the health monitor"""
        monitor = HealthMonitor(self.connection_manager)
        monitor.crud_operations = getattr(self, "crud_operations", None)  # type: ignore[attr-defined]
        return monitor

    @property
    def priority(self) -> ProviderPriority:
        """Provider priority for startup/shutdown"""
        return ProviderPriority.INFRASTRUCTURE

    @property  # type: ignore[no-redef]
    def database_type(self) -> str:
        """Get the database type from connection manager"""
        return self.connection_manager.database_type

    async def connect(self) -> None:
        """Establish connection to the database"""
        await self.connection_manager.connect()

    async def disconnect(self) -> None:
        """Close connection to the database"""
        await self.connection_manager.disconnect()

    async def is_connected(self) -> bool:
        """Check if database is connected"""
        return self.connection_manager.connected

    @abstractmethod
    async def _create_connection(self) -> Any:
        """Create a database connection (implementation-specific)"""

    @abstractmethod
    async def _close_connection(self, connection: Any) -> None:
        """Close a database connection (implementation-specific)"""

    @abstractmethod
    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute query and return raw results (implementation-specific)"""

    @abstractmethod
    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE and return affected rows (implementation-specific)"""

    @abstractmethod
    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        """Begin transaction (implementation-specific)"""

    @abstractmethod
    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction (implementation-specific)"""

    @abstractmethod
    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction (implementation-specific)"""

    @abstractmethod
    async def _get_last_insert_id(self, connection: Any, table: str) -> Any | None:
        """Get the last inserted ID (implementation-specific)"""

    async def execute_query(
        self,
        sql: str,
        params: list[Any] | None = None,
        **_kwargs: Any,
    ) -> QueryResult:
        """Execute a SELECT query"""
        return await self.crud_operations.execute_query(sql, params)

    async def execute_insert(
        self,
        table: str,
        data: dict[str, Any],
        **_kwargs: Any,
    ) -> InsertResult:
        """Execute an INSERT operation"""
        return await self.crud_operations.execute_insert(table, data)

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        where_clause: str,
        where_params: list[Any] | None = None,
        **_kwargs: Any,
    ) -> UpdateResult:
        """Execute an UPDATE operation"""
        return await self.crud_operations.execute_update(
            table,
            data,
            where_clause,
            where_params,
        )

    async def execute_delete(
        self,
        table: str,
        where_clause: str,
        where_params: list[Any] | None = None,
        **_kwargs: Any,
    ) -> DeleteResult:
        """Execute a DELETE operation"""
        return await self.crud_operations.execute_delete(
            table,
            where_clause,
            where_params,
        )

    async def execute_modify(
        self,
        sql: str,
        params: list[Any] | None = None,
        **_kwargs: Any,
    ) -> int:
        """Execute a non-SELECT query and return affected rows"""
        return await self.crud_operations.execute_modify(sql, params)

    async def execute(self, sql: str, params: Any = None) -> QueryResult:
        """Generic execute method that dispatches to query or modify based on content."""
        return await self.crud_operations.execute(sql, params)

    @abstractmethod  # type: ignore[no-redef]
    async def _get_last_insert_id(self, connection: Any, table: str) -> Any | None:
        """Get the last inserted ID (implementation-specific)"""

    def transaction(
        self, isolation_level: Any | None = None
    ) -> AbstractAsyncContextManager[Any]:
        """Context manager for transactions.

        Args:
            isolation_level: Optional isolation level to apply.
        """
        return self.transaction_manager.transaction(isolation_level)

    async def begin_transaction(self) -> None:
        """Begin a transaction"""
        await self.transaction_manager.begin_transaction()

    async def commit_transaction(self) -> None:
        """Commit current transaction"""
        await self.transaction_manager.commit_transaction()

    async def rollback_transaction(self) -> None:
        """Rollback current transaction"""
        await self.transaction_manager.rollback_transaction()

    # ------------------------------------------------------------------
    # DatabaseProviderProtocol connection/UoW contract
    #
    # The Protocol declares these methods with ``...`` placeholder bodies.
    # Subclassing it therefore *inherits the stubs* — without real
    # implementations here, ``driver.get_connection()`` silently returns
    # ``None`` (breaking ``async with provider.get_connection()``) and
    # ``driver.get_unit_of_work()`` returns ``None`` (corrupting the DI
    # registration that binds it as the scoped UoW factory).
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Any, None]:
        """Async context manager yielding a database connection.

        Satisfies the ``DatabaseProviderProtocol`` contract: yields a
        usable connection and guarantees its release on exit.

        Delegates to the driver's :class:`ConnectionManager`, which
        handles pool acquisition (with correct slot release), the
        ``connection.acquired`` hook, and the raw-connection fallback.

        Yields:
            A database connection.

        Example:
            >>> async with provider.get_connection() as conn:
            ...     await conn.execute("SELECT 1")
        """
        async with self.connection_manager.get_connection() as conn:
            yield conn

    def get_unit_of_work(self) -> Any:
        """Return a unit of work backed by this driver.

        Satisfies the ``DatabaseProviderProtocol`` contract — the
        inherited Protocol stub would otherwise return ``None``, and the
        DI registration (``container.scoped(UnitOfWorkProtocol,
        driver.get_unit_of_work)``) would bind a factory that resolves
        to ``None``.

        Note:
            Drivers have no request scope, so the returned UoW does not
            auto-commit/rollback on context-manager exit (that behaviour
            is scope-driven via ``DatabaseService.scoped_context``).
            Call ``commit()`` / ``rollback()`` explicitly.
        """
        # Local import: managers.manager TYPE_CHECKING-imports this package.
        from quadkit.sql.managers.manager import ScopedUnitOfWork

        return ScopedUnitOfWork(self)

    def get_current_context(self) -> dict[str, Any] | None:
        """Drivers have no request scope — there is never an active one."""
        return None

    @property
    def provider(self) -> Any:
        """Self-reference so UoW plumbing (``manager.provider``) resolves.

        ``ScopedUnitOfWork`` accesses ``self.manager.provider.db_provider``
        for commit/rollback routing; for a driver the manager *is* the
        driver, so the provider reference is itself.
        """
        return self

    @property
    def db_provider(self) -> Any:
        """Self-reference: the driver is its own underlying database provider."""
        return self

    async def commit(self) -> None:
        """Commit the current transaction.

        Alias for :meth:`commit_transaction` — the name the UoW and
        ``DatabaseService`` transaction plumbing call when a provider
        exposes a short-form ``commit`` API.
        """
        await self.commit_transaction()

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Alias for :meth:`rollback_transaction` — the short-form name
        expected by UoW/transaction plumbing.
        """
        await self.rollback_transaction()

    # Schema operations
    def get_repository(self, model_class: Any) -> Any:
        """Get or create a repository for the given model class"""
        if not hasattr(self, "_repositories"):
            self._repositories = {}

        if model_class not in self._repositories:
            # Local import to avoid circular dependency
            from quadkit.sql.orm import (
                ModelRepository,
            )

            self._repositories[model_class] = ModelRepository(model_class, self)
        return self._repositories[model_class]

    def query(self, table: str) -> Any:
        """Return a SELECT query builder for the given table"""
        return self.query_builder_manager.query(table)

    def insert(self, table: str, data: dict[str, Any]) -> Any:
        """Return an INSERT query builder for the given table and data"""
        return self.query_builder_manager.insert(table, data)

    def update(self, table: str, data: dict[str, Any]) -> Any:
        """Return an UPDATE query builder for the given table and data"""
        return self.query_builder_manager.update(table, data)

    def delete(self, table: str) -> Any:
        """Return a DELETE query builder for the given table"""
        return self.query_builder_manager.delete(table)

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        return await self.schema_manager.table_exists(table_name)

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for a table"""
        return await self.schema_manager.get_table_columns(table_name)

    async def create_table(self, table_name: str, columns: dict[str, str]) -> None:
        """Create a table with given columns"""
        await self.schema_manager.create_table(table_name, columns)

    async def drop_table(self, table_name: str) -> None:
        """Drop a table"""
        await self.schema_manager.drop_table(table_name)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check"""
        return await self.health_monitor.health_check()

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics (merge provider-level state with health monitor)."""
        stats = await self.health_monitor.get_stats()
        # Provider-level attributes override monitor-derived values when present
        stats["connected"] = await self.is_connected()
        stats["connection_pool"] = self.connection_pool is not None
        stats["query_logger"] = (
            getattr(self, "query_executor", None) is not None
            and getattr(self.query_executor, "query_logger", None) is not None
        )
        return stats
