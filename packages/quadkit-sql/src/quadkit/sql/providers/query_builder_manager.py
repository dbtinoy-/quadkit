"""
Query builder integration for database providers.

Handles integration with query builders for fluent query construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.sql_dialect import SQLDialect

logger = get_logger(__name__)


class DialectHandler(Protocol):
    """Protocol for SQL dialect handlers."""

    def get_dialect(self) -> SQLDialect: ...


class PostgresDialectHandler:
    """Handler for PostgreSQL dialect."""

    def get_dialect(self) -> SQLDialect:
        from quadkit.contracts.data.sql.sql_dialect import (
            SQLDialect,
        )

        return SQLDialect.POSTGRESQL


class SQLiteDialectHandler:
    """Handler for SQLite dialect."""

    def get_dialect(self) -> SQLDialect:
        from quadkit.contracts.data.sql.sql_dialect import (
            SQLDialect,
        )

        return SQLDialect.SQLITE


class MySQLDialectHandler:
    """Handler for MySQL dialect."""

    def get_dialect(self) -> SQLDialect:
        from quadkit.contracts.data.sql.sql_dialect import (
            SQLDialect,
        )

        return SQLDialect.MYSQL


class SQLDialectRegistry:
    """Registry for SQL dialect handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, DialectHandler] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, DialectHandler]:
        """Declare the built-in dialect handlers, by exact DB type name."""
        return {
            "postgresql": PostgresDialectHandler(),
            "postgres": PostgresDialectHandler(),
            "sqlite": SQLiteDialectHandler(),
            "mysql": MySQLDialectHandler(),
        }

    @classmethod
    def with_defaults(cls) -> SQLDialectRegistry:
        """Create a registry pre-populated with the built-in handlers."""
        registry = cls()
        for key, handler in cls._default_entries().items():
            registry.register_handler(key, handler)
        return registry

    def register_handler(self, database_type: str, handler: DialectHandler) -> None:
        """Register a dialect handler."""
        self._handlers[database_type] = handler

    def get_dialect(self, database_type: str) -> SQLDialect:
        """Get SQL dialect for the given database type."""
        from quadkit.contracts.data.sql.sql_dialect import (
            SQLDialect,
        )

        handler = self._handlers.get(database_type)
        if handler:
            return handler.get_dialect()
        # Default to PostgreSQL
        return SQLDialect.POSTGRESQL


# Global dialect registry
_dialect_registry = SQLDialectRegistry.with_defaults()


class QueryBuilderManager:
    """
    Manages query builder integration.

    This class provides integration with query builders for
    fluent database query construction.
    """

    def __init__(self, crud_operations: Any) -> None:
        self.crud_operations = crud_operations

    def _get_dialect(self) -> SQLDialect:
        """Get the SQL dialect for this provider using the registry"""
        database_type = getattr(self, "database_type", "sqlite")
        return _dialect_registry.get_dialect(database_type)

    def _create_managed_builder(
        self,
        table: str,
        mode: str = "select",
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Helper to create a managed query builder"""
        from quadkit.sql.query import (
            AsyncQueryBuilder,
        )

        class ManagedQueryBuilder(AsyncQueryBuilder):
            def __init__(self, table: str, provider: Any, dialect: Any) -> None:
                super().__init__(table, dialect)
                self.provider = provider

            async def execute(self, conn: Any = None) -> Any:
                # If conn is provided, use it (assumed to be driver connection),
                # otherwise use provider's execute wrapper
                if conn:
                    return await super().execute(conn)

                query = self.build()
                return await self.provider.crud_operations.execute(
                    query.sql,
                    list(query.params),
                )

        builder = ManagedQueryBuilder(table, self, self._get_dialect())

        if mode == "insert" and data:
            builder.insert(data)
        elif mode == "update" and data:
            builder.update(data)
        elif mode == "delete":
            builder.delete()
        # default is select (already set in __init__)

        return builder

    def query(self, table: str) -> Any:
        """Return a SELECT query builder for the given table"""
        return self._create_managed_builder(table, "select")

    def insert(self, table: str, data: dict[str, Any]) -> Any:
        """Return an INSERT query builder for the given table and data"""
        return self._create_managed_builder(table, "insert", data)

    def update(self, table: str, data: dict[str, Any]) -> Any:
        """Return an UPDATE query builder for the given table and data"""
        return self._create_managed_builder(table, "update", data)

    def delete(self, table: str) -> Any:
        """Return a DELETE query builder for the given table"""
        return self._create_managed_builder(table, "delete")
