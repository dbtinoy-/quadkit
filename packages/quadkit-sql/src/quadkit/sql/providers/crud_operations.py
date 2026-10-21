"""
CRUD operations for database providers.

Handles high-level database operations like insert, update, delete, and select.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.contracts.data.sql.database import encode_bind_value
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql import DeleteResult, InsertResult, QueryResult, UpdateResult
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    import types


def _serialize_param(value: Any) -> Any:
    """Encode a JSON-shaped value for driver binding.

    Thin alias over the contract's
    :func:`~quadkit.contracts.data.sql.database.encode_bind_value`: the rule
    ("encode ``dict``/``list`` to JSON text before binding") belongs to
    ``DatabaseProviderProtocol``, not to this package, so every provider —
    including implementations outside ``quadkit-sql`` — shares one definition.
    Kept under its historical private name for the call sites below.

    Args:
        value: Value about to be bound to a driver parameter.

    Returns:
        The value unchanged, or its JSON text encoding when it is a
        ``dict`` or ``list``.
    """
    return encode_bind_value(value)


@dataclass
class OperationResult:
    """Result of a database operation."""

    success: bool
    execution_time: float
    error_message: str | None = None
    affected_rows: int = 0
    inserted_id: Any = None


class DatabaseOperationContext:
    """Context manager for database operations with timing and error handling.

    Responsibilities are deliberately narrow: acquire/release the connection,
    measure wall-clock time for the whole operation, and normalise errors to
    :class:`DatabaseError`.  Query logging is **not** done here — the query
    executor's ``execute_query``/``execute_modify`` already emit exactly one
    log entry per statement, and logging here as well used to produce
    duplicate console lines for every INSERT/UPDATE/DELETE.
    """

    def __init__(
        self,
        connection_manager: Any,
        query_executor: Any,
        sql: str,
        params: Any = None,
    ):
        self.connection_manager = connection_manager
        self.query_executor = query_executor
        self.sql = sql
        self.params = params
        self.start_time = ambient_clock.monotonic()
        self.execution_time = 0.0

    async def __aenter__(self) -> Any:
        self.conn_cm = self.connection_manager.get_connection()
        self.conn = await self.conn_cm.__aenter__()
        return self.conn

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.execution_time = ambient_clock.monotonic() - self.start_time

        # Close the connection
        await self.conn_cm.__aexit__(exc_type, exc_val, exc_tb)

        if exc_val:
            raise DatabaseError(str(exc_val)) from exc_val

    def get_execution_time(self) -> float:
        return self.execution_time


class CrudOperations(ABC):
    """
    Handles CRUD (Create, Read, Update, Delete) operations.

    This class provides high-level database operations that build on
    the lower-level query execution capabilities.
    """

    def __init__(
        self,
        query_executor: Any,
        connection_manager: Any,
    ) -> None:
        self.query_executor = query_executor
        self.connection_manager = connection_manager

    @abstractmethod
    async def _get_last_insert_id(self, connection: Any, table: str) -> Any | None:
        """Get the last inserted ID (implementation-specific)"""

    async def execute_insert(
        self,
        table: str,
        data: dict[str, Any],
    ) -> InsertResult:
        """Execute an INSERT operation"""
        safe_table = Table(table)
        safe_columns = ", ".join(str(Column(c)) for c in data)
        columns = safe_columns
        placeholders = ", ".join("?" for _ in data)
        values = [_serialize_param(v) for v in data.values()]

        sql = f"INSERT INTO {safe_table} ({columns}) VALUES ({placeholders})"  # noqa: S608 -- safe_table/columns are Table()/Column() quoted identifiers, values parameterized

        ctx = DatabaseOperationContext(
            self.connection_manager,
            self.query_executor,
            sql,
            values,
        )
        async with ctx:
            affected_rows = await self.query_executor.execute_modify(
                ctx.conn,
                sql,
                values,
            )
            inserted_id = await self._get_last_insert_id(ctx.conn, safe_table)  # type: ignore[arg-type]

        return InsertResult(
            inserted_id=inserted_id,
            affected_rows=affected_rows,
            execution_time=ctx.get_execution_time(),
            success=True,
        )

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        where_clause: str,
        where_params: list[Any] | None = None,
    ) -> UpdateResult:
        """Execute an UPDATE operation"""
        safe_table = Table(table)
        set_clause = ", ".join(f"{Column(k)} = ?" for k in data)
        values = [_serialize_param(v) for v in data.values()]

        sql = f"UPDATE {safe_table} SET {set_clause} WHERE {where_clause}"  # noqa: S608 -- safe_table/set_clause are Table()/Column() quoted; where_clause built by repo mixins from validated identifiers

        if where_params:
            values.extend(where_params)

        ctx = DatabaseOperationContext(
            self.connection_manager,
            self.query_executor,
            sql,
            values,
        )
        async with ctx:
            affected_rows = await self.query_executor.execute_modify(
                ctx.conn,
                sql,
                values,
            )

        return UpdateResult(
            affected_rows=affected_rows,
            execution_time=ctx.get_execution_time(),
            success=True,
        )

    async def execute_delete(
        self,
        table: str,
        where_clause: str,
        where_params: list[Any] | None = None,
    ) -> DeleteResult:
        """Execute a DELETE operation"""
        safe_table = Table(table)
        sql = f"DELETE FROM {safe_table} WHERE {where_clause}"  # noqa: S608 -- safe_table is a Table() quoted identifier; where_clause built by repo mixins from validated identifiers

        ctx = DatabaseOperationContext(
            self.connection_manager,
            self.query_executor,
            sql,
            where_params,
        )
        async with ctx:
            affected_rows = await self.query_executor.execute_modify(
                ctx.conn,
                sql,
                where_params,
            )

        return DeleteResult(
            affected_rows=affected_rows,
            execution_time=ctx.get_execution_time(),
            success=True,
        )

    async def execute_query(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> QueryResult:
        """Execute a SELECT query"""
        async with self.connection_manager.get_connection() as conn:
            return cast(
                "QueryResult",
                await self.query_executor.execute_query(conn, sql, params),
            )

    async def execute_modify(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute a non-SELECT query and return affected rows"""
        async with self.connection_manager.get_connection() as conn:
            return cast(
                "int", await self.query_executor.execute_modify(conn, sql, params)
            )

    async def execute(self, sql: str, params: Any = None) -> QueryResult:
        """Generic execute method that dispatches to query or modify based on content."""
        sql_upper = sql.strip().upper()
        # If it's a SELECT or has RETURNING, we expect rows back
        if sql_upper.startswith("SELECT") or "RETURNING" in sql_upper:
            return await self.execute_query(sql, params)

        # Otherwise it's a mutation. We use execute_modify but wrap it in a QueryResult
        # to satisfy the protocol and ensure commit happens in SQLite.
        start_time = ambient_clock.monotonic()
        success = False
        error_message = None
        affected_rows = 0

        try:
            affected_rows = await self.execute_modify(sql, params)
            success = True
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            RuntimeError,
            OSError,
            ConnectionError,
            TimeoutError,
        ) as e:
            error_message = str(e)
            raise
        finally:
            execution_time = ambient_clock.monotonic() - start_time
            # Note: execute_modify already logs, so we don't double log here

        return QueryResult(
            rows=[],
            row_count=affected_rows,
            execution_time=execution_time,
            success=success,
            error_message=error_message,
        )
