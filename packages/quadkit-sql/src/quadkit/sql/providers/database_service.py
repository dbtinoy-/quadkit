"""Database provider for Quadkit Framework integration (Consolidated).

This module provides a unified DatabaseService that integrates with multiple
database backends (SQLite, PostgreSQL, MySQL). It provides connection pooling,
transaction management, resilience patterns (retry, circuit breaker), and
query logging.

Example:
    Using DatabaseService with PostgreSQL::

        from quadkit.sql.providers.database_service import DatabaseService
        from quadkit.sql.config import DatabaseConfig

        config = DatabaseConfig.from_url("postgresql://user:pass@localhost/mydb")
        provider = DatabaseService(config=config)

        # In your application:
        async with provider.transaction():
            await provider.execute_query("SELECT * FROM users")

    Using with DI container::

        from quadkit.sql.di.provider import DatabaseProvider
        di_provider = DatabaseProvider(config="postgresql://user:pass@localhost/mydb")
        await di_provider.register(container)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from quadkit.sql.config import DatabaseConfig
from quadkit.sql.logging import ConsoleQueryLogger
from quadkit.sql.managers import DatabaseManager
from quadkit.sql.providers._connection_mixin import _ConnectionMixin
from quadkit.sql.providers._health_mixin import _HealthMixin
from quadkit.sql.providers._query_mixin import _QueryMixin
from quadkit.sql.resilience import DatabaseResilienceHandler

if TYPE_CHECKING:
    from quadkit.contracts import (
        ConnectionPoolProtocol,
        DatabaseProviderProtocol,
        MigrationManagerProtocol,
        QueryLoggerProtocol,
    )
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.primitives.context import Context

ProviderFactory = Any


def _load_sqlite(url: str, **kwargs: Any) -> DatabaseProviderProtocol:
    from quadkit.sql.providers.sqlite_provider import SQLiteProvider

    return SQLiteProvider(url, **kwargs)  # type: ignore[abstract]


def _load_postgres(url: str, **kwargs: Any) -> DatabaseProviderProtocol:
    from quadkit.sql.providers.postgres_provider import (
        PostgresProvider,
    )

    return PostgresProvider(url, **kwargs)  # type: ignore[abstract]


def _load_mysql(url: str, **kwargs: Any) -> DatabaseProviderProtocol:
    from quadkit.sql.providers.mysql_provider import MySQLProvider

    return MySQLProvider(url, **kwargs)  # type: ignore[abstract]


class DatabaseService(_ConnectionMixin, _QueryMixin, _HealthMixin):
    """Database facade that manages a database driver and its lifecycle.

    Wraps a DatabaseDriver (engine-specific driver) and provides
    connection pooling, transaction management, resilience patterns, and
    query logging. For registering this into the DI container, see
    ``DatabaseProvider`` in ``di_provider.py``.

    Delegates specialized logic to:
    - _ConnectionMixin: Connection lifecycle, transactions, and scoped contexts.
    - _QueryMixin: Query execution and result normalisation.
    - _HealthMixin: Health checks and table existence.
    - DatabaseManager: Scoped connections, UoW, and pooling.
    - DatabaseResilienceHandler: Retry and circuit breaker pipelines.
    - Driver-specific protocols: SQLite, Postgres, MySQL, etc.

    Example:
        Basic usage::

            provider = DatabaseService(url="postgresql://localhost/mydb")
            await provider.boot()
            result = await provider.execute_query("SELECT * FROM users")
            await provider.shutdown()

        Using transactions::

            async with provider.transaction():
                await provider.execute_insert("users", {"name": "John"})
                await provider.execute_update("users", {"name": "Jane"}, "id = ?", (1,))
    """

    _driver_registry: ClassVar[dict[str, ProviderFactory]] = {
        "sqlite": _load_sqlite,
        "postgres": _load_postgres,
        "mysql": _load_mysql,
    }

    @classmethod
    def register_driver(cls, name: str, loader: ProviderFactory) -> None:
        """Register a database driver loader by name.

        Args:
            name: The driver name (e.g., "sqlite", "postgres", "mysql").
            loader: A callable that returns a DatabaseProviderProtocol instance.
        """
        cls._driver_registry[name] = loader

    @classmethod
    def get_driver_loader(cls, name: str) -> ProviderFactory | None:
        """Get a driver loader by name.

        Args:
            name: The driver name to look up.

        Returns:
            The driver loader function or None if not found.
        """
        return cls._driver_registry.get(name)

    def __init__(
        self,
        config: DatabaseConfig | str | None = None,
        connection_pool: ConnectionPoolProtocol | None = None,
        query_logger: QueryLoggerProtocol | None = None,
        migration_manager: MigrationManagerProtocol | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the DatabaseService.

        Args:
            config: DatabaseConfig instance or connection URL string.
            connection_pool: Optional connection pool implementation.
            query_logger: Optional query logger for debugging.
            migration_manager: Optional migration manager for schema changes.
            **kwargs: Additional provider-specific options.
        """
        if config is None:
            config = kwargs.get("url") or kwargs.get("dsn") or "sqlite:///:memory:"

        if isinstance(config, str):
            config = DatabaseConfig.from_url(config)

        self.name = config.name
        self.config = config

        self._explicit_provider_type = kwargs.get("provider_type")
        self.kwargs = kwargs

        self.db_provider: DatabaseProviderProtocol | None = None
        self.connection_pool = connection_pool
        self.query_logger = query_logger or ConsoleQueryLogger()
        self.migration_manager = migration_manager

        self.manager = DatabaseManager(self)
        self.resilience_handler = DatabaseResilienceHandler()

        if "retry_config" in kwargs:
            self.resilience_handler.retry_config = kwargs["retry_config"]

        self.metrics = kwargs.get("metrics")
        self.tracer = kwargs.get("tracer")

        self._context: Context | None = None
        self._started = False
        self._pipeline = None
        # Pool context managers tracked by acquire() outside a scope, so
        # release() can return the slot (id(conn) -> context manager).
        self._manual_connections: dict[int, Any] = {}

    @property
    def database_type(self) -> str:
        """Return the type of database (e.g., 'postgres', 'sqlite')."""
        if self.db_provider and hasattr(self.db_provider, "database_type"):
            return cast("str", self.db_provider.database_type)

        # Fallback to config inference if provider not yet started
        return self._infer_provider_type(
            str(self.config.url if hasattr(self.config, "url") else self.config)
        )

    def _infer_provider_type(self, url: str) -> str:
        """Infer the database provider type from the connection URL.

        Args:
            url: The database connection URL.

        Returns:
            The provider type string (e.g., "sqlite", "postgres").
        """
        if url.startswith(("mongodb://", "mongodb+srv://")):
            from quadkit.contracts.exceptions.config import ConfigurationError

            raise ConfigurationError(
                "MongoDB URLs are not supported by quadkit-sql. "
                "Use the optional provider instead: from the optional provider module import NoSQLProvider"
            )

        from quadkit.sql.lib import infer_provider_type_from_url

        return infer_provider_type_from_url(url)

    def set_context(self, context: Context | None) -> None:
        """Attach an optional shared request context to query logging."""
        self._context = context
        if self.db_provider is not None:
            qe = getattr(self.db_provider, "query_executor", None)
            if qe is not None:
                qe._context = context

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry to the service runtime path."""
        self._hook_registry = hooks
        self.manager.set_hook_registry(hooks)
        self._propagate_hook_registry()

    def _propagate_hook_registry(self) -> None:
        """Propagate the current hook registry into driver managers."""
        if self.db_provider is None:
            return

        connection_manager = getattr(self.db_provider, "connection_manager", None)
        if connection_manager is not None and hasattr(
            connection_manager,
            "set_hook_registry",
        ):
            connection_manager.set_hook_registry(self._hook_registry)

        transaction_manager = getattr(self.db_provider, "transaction_manager", None)
        if transaction_manager is not None and hasattr(
            transaction_manager,
            "set_hook_registry",
        ):
            transaction_manager.set_hook_registry(self._hook_registry)

    @classmethod
    def from_config(cls, config: DatabaseConfig, **context: Any) -> DatabaseService:
        """Create a DatabaseService from a DatabaseConfig.

        Args:
            config: The database configuration.
            **context: Additional context options.

        Returns:
            A new DatabaseService instance.
        """
        return cls(
            config=config,
            connection_pool=context.get("connection_pool"),
            query_logger=context.get("query_logger"),
            migration_manager=context.get("migration_manager"),
            **context,
        )

    # --- DatabaseProviderProtocol delegation ---

    async def connect(self) -> None:
        """Establish connection to the database."""
        if self.db_provider is not None:
            await self.db_provider.connect()

    async def disconnect(self) -> None:
        """Close connection to the database."""
        if self.db_provider is not None:
            await self.db_provider.disconnect()

    async def get_primary_pool(self) -> ConnectionPoolProtocol:
        """Return the primary connection pool."""
        if self.db_provider is not None:
            pool: ConnectionPoolProtocol = await self.db_provider.get_primary_pool()
            return pool
        if self.connection_pool is not None:
            return self.connection_pool
        msg = "No database provider or connection pool available"
        raise RuntimeError(msg)
