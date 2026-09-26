"""
PostgreSQL database provider for community edition
"""

from __future__ import annotations

from typing import Any

from quadkit import serialization as json

asyncpg: Any
try:
    import asyncpg as _asyncpg

    asyncpg = _asyncpg
except ImportError:
    asyncpg = None

from quadkit.contracts.data.identifiers import validate_identifier
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    CheckConstraintError,
    DatabaseConnectionError,
    DuplicateKeyError,
    ForeignKeyError,
    IntegrityError,
    QueryError,
)
from quadkit.sql.providers.base_provider import (
    DatabaseDriver,
)

logger = get_logger(__name__)


class PostgresProvider(DatabaseDriver):
    """
    PostgreSQL database provider implementation

    Uses asyncpg for async PostgreSQL operations.
    """

    name = "postgres"

    def __init__(self, connection_string: str, **kwargs: Any) -> None:
        super().__init__(connection_string, **kwargs)

    async def _create_connection(self) -> Any:
        """Create PostgreSQL connection"""
        # Parse connection string for asyncpg
        conn_kwargs = {
            "host": self.connection_manager.host,
            "port": self.connection_manager.port,
            "user": self.connection_manager.username,
            "password": self.connection_manager.password,
            "database": self.connection_manager.database,
        }

        # Filter out None values
        conn_kwargs = {k: v for k, v in conn_kwargs.items() if v is not None}

        try:
            conn = await asyncpg.connect(**conn_kwargs)
        except asyncpg.InvalidCatalogNameError:
            # Database doesn't exist, try to create it
            target_db = conn_kwargs.get("database")
            if not isinstance(target_db, str):
                raise ConnectionError(
                    "Cannot auto-create database: 'database' connect kwarg "
                    f"is missing or not a string (got {target_db!r})"
                ) from None
            logger.info(
                "Database '%s' does not exist. Attempting to create it...", target_db
            )

            # Connect to default 'postgres' database to run CREATE DATABASE
            admin_kwargs = conn_kwargs.copy()
            admin_kwargs["database"] = "postgres"

            try:
                admin_conn = await asyncpg.connect(**admin_kwargs)
                try:
                    # CREATE DATABASE cannot run in a transaction block
                    await admin_conn.execute(
                        f'CREATE DATABASE "{validate_identifier(target_db)}"'
                    )
                    logger.info("Successfully created database '%s'", target_db)
                finally:
                    await admin_conn.close()

                # Retry connection to the newly created database
                conn = await asyncpg.connect(**conn_kwargs)
            except Exception as create_err:  # noqa: BLE001 — any auto-creation failure becomes the documented ConnectionError
                logger.error(
                    "Failed to auto-create database '%s': %s", target_db, create_err
                )
                raise ConnectionError(
                    f"Database '{target_db}' does not exist and auto-creation failed"
                ) from create_err

        # Register JSONB codec - the encoder MUST return str (not bytes)
        # because asyncpg format='text' (the default) expects str.
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps_str,
            decoder=json.loads,
            schema="pg_catalog",
        )
        return conn

    async def _close_connection(self, connection: Any) -> None:
        """Close PostgreSQL connection"""
        await connection.close()

    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SELECT query"""
        try:
            if isinstance(params, dict):
                # Named parameters with $param syntax
                rows = await connection.fetch(sql, **params)
            else:
                # Positional parameters with ? converted to $1, $2, etc.
                sql = self._convert_sql(sql)
                rows = await connection.fetch(sql, *(params or []))
            return [dict(row) for row in rows]
        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            asyncpg.InternalClientError,
        ) as e:
            self._handle_postgres_error(e, sql, params)
            raise

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | dict[str, Any] | None = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE"""
        try:
            if isinstance(params, dict):
                # Named parameters with $param syntax
                result = await connection.execute(sql, **params)
            else:
                # Positional parameters with ? converted to $1, $2, etc.
                sql = self._convert_sql(sql)
                result = await connection.execute(sql, *(params or []))
            # Parse affected rows from result string like "UPDATE 5" or "INSERT 0 1"
            parts = result.split()
            if len(parts) >= 2 and parts[0] in ["UPDATE", "DELETE", "INSERT"]:
                try:
                    return int(parts[-1])
                except ValueError:
                    pass
            return 0
        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            asyncpg.InternalClientError,
        ) as e:
            self._handle_postgres_error(e, sql, params)
            raise

    def _handle_postgres_error(
        self,
        e: Any,
        sql: str | None = None,
        params: Any = None,
    ) -> None:
        """Translate PostgreSQL exceptions to Quadkit exceptions"""
        msg = str(e)
        if not asyncpg:
            raise e

        if isinstance(e, asyncpg.IntegrityConstraintViolationError):
            if isinstance(e, asyncpg.UniqueViolationError):
                raise DuplicateKeyError(msg, cause=e) from e
            if isinstance(e, asyncpg.ForeignKeyViolationError):
                raise ForeignKeyError(msg, cause=e) from e
            if isinstance(e, asyncpg.CheckViolationError):
                raise CheckConstraintError(msg, cause=e) from e
            raise IntegrityError(msg, cause=e) from e

        if isinstance(e, (asyncpg.InterfaceError, asyncpg.InternalClientError)):
            raise DatabaseConnectionError(msg, cause=e) from e

        raise QueryError(msg, sql=sql, params=params, cause=e) from e

    def _convert_sql(self, sql: str) -> str:
        """Convert standard SQL placeholders (?) to PostgreSQL ($n)"""
        if "?" not in sql:
            return sql

        parts = sql.split("?")
        if len(parts) == 1:
            return sql

        res = []
        for i, part in enumerate(parts[:-1]):
            res.append(part)
            res.append(f"${i + 1}")
        res.append(parts[-1])
        return "".join(res)

    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        """Begin transaction with optional isolation level."""
        await connection.execute("BEGIN")
        if isolation is not None:
            await connection.execute(
                f"SET TRANSACTION ISOLATION LEVEL {isolation.value}"
            )

    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction"""
        await connection.execute("COMMIT")

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction"""
        await connection.execute("ROLLBACK")

    async def _get_last_insert_id(self, connection: Any, _table: str) -> Any | None:
        """Get last inserted ID using RETURNING or currval"""
        return None

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists in PostgreSQL"""
        result = await self.execute_query(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            [table_name],
        )
        return bool(result.rows[0]["exists"]) if result.rows else False

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for PostgreSQL table"""
        sql = """
        SELECT
            column_name as name,
            data_type as type,
            is_nullable = 'YES' as nullable,
            column_default as default,
            is_identity = 'YES' as primary_key
        FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
        """
        result = await self.execute_query(sql, [table_name])
        return result.rows
