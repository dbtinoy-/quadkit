"""
MySQL database provider for community edition
"""

from __future__ import annotations

from typing import Any

aiomysql: Any
try:
    import aiomysql as _aiomysql

    aiomysql = _aiomysql
except ImportError:
    aiomysql = None

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


class MySQLProvider(DatabaseDriver):
    """
    MySQL database provider implementation

    Uses aiomysql for async MySQL operations.
    """

    name = "mysql"

    def __init__(self, connection_string: str, **kwargs: Any) -> None:
        super().__init__(connection_string, **kwargs)

    async def _create_connection(self) -> Any:
        """Create MySQL connection"""
        # Parse connection string for aiomysql
        conn_kwargs = {
            "host": self.host,  # type: ignore[attr-defined]
            "port": self.port or 3306,  # type: ignore[attr-defined]
            "user": self.username,  # type: ignore[attr-defined]
            "password": self.password,  # type: ignore[attr-defined]
            "db": self.database,  # type: ignore[attr-defined]
            "autocommit": True,  # We'll handle transactions manually
        }
        # Filter out None values
        conn_kwargs = {k: v for k, v in conn_kwargs.items() if v is not None}

        return await aiomysql.connect(**conn_kwargs)

    async def _close_connection(self, connection: Any) -> None:
        """Close MySQL connection"""
        connection.close()

    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SELECT query"""
        try:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params or [])
                rows: list[dict[str, Any]] = await cursor.fetchall()
                return rows
        except aiomysql.Error as e:
            self._handle_mysql_error(e, sql, params)
            raise

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE"""
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params or [])
                # Only commit immediately if not inside an explicit transaction
                if not self.transaction_manager.in_transaction:
                    await connection.commit()
                rowcount: int = cursor.rowcount
                return rowcount
        except aiomysql.Error as e:
            self._handle_mysql_error(e, sql, params)
            raise

    def _handle_mysql_error(
        self,
        e: Any,
        sql: str | None = None,
        params: Any = None,
    ) -> None:
        """Translate MySQL exceptions to Quadkit exceptions"""
        msg = str(e)
        if not aiomysql:
            raise e

        # Error codes for categorization
        # 1062: Duplicate entry
        # 1216, 1217: Foreign key constraint fails
        # 1451, 1452: Foreign key constraint fails
        # 4025: Check constraint fails (MariaDB/MySQL 8.0.16+)
        errno = getattr(e, "args", [0])[0] if hasattr(e, "args") else 0

        if errno == 1062:
            raise DuplicateKeyError(msg, cause=e) from e
        if errno in [1216, 1217, 1451, 1452]:
            raise ForeignKeyError(msg, cause=e) from e
        if errno == 4025:
            raise CheckConstraintError(msg, cause=e) from e

        if isinstance(e, aiomysql.IntegrityError):
            raise IntegrityError(msg, cause=e) from e

        if isinstance(e, (aiomysql.OperationalError, aiomysql.InterfaceError)):
            # Check for connection-related errors
            if errno in [2002, 2003, 2006, 2013]:
                raise ConnectionError(msg) from e
            raise DatabaseConnectionError(msg, cause=e) from e

        raise QueryError(msg, sql=sql, params=params, cause=e) from e

    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        """Begin transaction with optional isolation level (MySQL requires level before BEGIN)."""
        if isolation is not None:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SET TRANSACTION ISOLATION LEVEL {isolation.value}"
                )
        await connection.begin()

    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction"""
        await connection.commit()

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction"""
        await connection.rollback()

    async def _get_last_insert_id(self, connection: Any, _table: str) -> Any | None:
        """Get last inserted ID"""
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT LAST_INSERT_ID()")
            result = await cursor.fetchone()
            return result[0] if result else None

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists in MySQL"""
        result = await self.execute_query(
            "SELECT COUNT(*) as count FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [table_name],
        )
        if result.rows and result.rows[0]:
            count = result.rows[0].get("count", 0)
            return int(count) > 0
        return False

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for MySQL table"""
        sql = """
        SELECT
            COLUMN_NAME as name,
            DATA_TYPE as type,
            IS_NULLABLE = 'YES' as nullable,
            COLUMN_DEFAULT as default,
            COLUMN_KEY = 'PRI' as primary_key
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """
        result = await self.execute_query(sql, [table_name])
        return result.rows if result.rows else []
