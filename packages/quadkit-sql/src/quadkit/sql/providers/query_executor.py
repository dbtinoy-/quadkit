"""
Query execution and logging for database providers.

Handles raw query execution, result processing, and query logging.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.primitives.context import Context, get_request_context
from quadkit.sql import QueryLogEntry, QueryLoggerProtocol, QueryResult
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

logger = get_logger(__name__)


class QueryExecutor(ABC):
    """
    Handles query execution and logging.

    This class manages the execution of database queries, result processing,
    and comprehensive query logging with performance metrics.
    """

    def __init__(
        self,
        query_logger: QueryLoggerProtocol | None = None,
        context: Context | None = None,
    ) -> None:
        self.query_logger = query_logger
        self._context = context

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

    async def _log_query(
        self,
        sql: str,
        params: list[Any] | None,
        execution_time: float,
        success: bool,
        error_message: str | None = None,
        connection_id: str | None = None,
        transaction_id: str | None = None,
    ) -> None:
        """Log query execution if logger is available"""
        if self.query_logger is None:
            return

        current = (
            get_request_context(self._context.registry)
            if self._context is not None
            else None
        )
        entry = QueryLogEntry(
            sql=sql,
            params=tuple(params) if params is not None else None,
            execution_time=execution_time,
            timestamp=ambient_clock.now(),
            success=success,
            error_message=error_message,
            connection_id=connection_id,
            transaction_id=transaction_id,
            user_id=current.user_id if current is not None else None,
            request_id=current.request_id if current is not None else None,
            trace_id=current.trace_id if current is not None else None,
        )
        await self.query_logger.log_query(entry)

    async def execute_query(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> QueryResult:
        """Execute a SELECT query"""
        start_time = ambient_clock.timestamp()
        success = False
        error_message = None
        rows = []

        try:
            rows = await self._execute_query_raw(connection, sql, params)
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
            logger.exception("Query execution failed: %s", error_message)
            raise
        finally:
            execution_time = (ambient_clock.timestamp()) - start_time
            await self._log_query(sql, params, execution_time, success, error_message)

        return QueryResult(
            rows=rows,
            row_count=len(rows),
            execution_time=execution_time,
            success=success,
            error_message=error_message,
        )

    async def execute_modify(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute a non-SELECT query and return affected rows"""
        start_time = ambient_clock.timestamp()
        success = False
        error_message = None
        affected_rows = 0

        try:
            affected_rows = await self._execute_modify_raw(connection, sql, params)
            success = True
            return affected_rows
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
            logger.exception("Modify execution failed: %s", error_message)
            raise
        finally:
            execution_time = (ambient_clock.timestamp()) - start_time
            await self._log_query(sql, params, execution_time, success, error_message)
