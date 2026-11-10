"""
Query execution and logging for database providers.

Handles raw query execution, result processing, and query logging.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Any

from quadkit.logging import get_logger, safe_error_type
from quadkit.primitives import clock as ambient_clock
from quadkit.primitives.context import Context
from quadkit.sql import QueryLogEntry, QueryLoggerProtocol, QueryResult
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

logger = get_logger(__name__)

_SQL_LOG_REDACTION = re.compile(
    r"(?P<comment>--[^\r\n]*|/\*.*?\*/)"
    r"|(?P<dollar_string>(?P<delimiter>\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$).*?(?P=delimiter))"
    r"|(?P<string>'(?:''|\\.|[^'])*')"
    r"|(?P<number>(?<![A-Za-z0-9_$?])[-+]?(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?![A-Za-z0-9_$?]))",
    re.DOTALL,
)


def _sanitize_sql_for_logging(sql: str) -> str:
    """Preserve SQL shape while removing inline literals and comments."""
    return _SQL_LOG_REDACTION.sub(
        lambda match: " " if match.lastgroup == "comment" else "?",
        sql,
    )


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

        entry = QueryLogEntry(
            sql=_sanitize_sql_for_logging(sql),
            # Bind values and request-scoped identifiers can contain sensitive
            # user data. Preserve only the SQL structure for diagnostics.
            params=None,
            execution_time=execution_time,
            timestamp=ambient_clock.now(),
            success=success,
            error_message=error_message,
            connection_id=None,
            transaction_id=None,
            user_id=None,
            request_id=None,
            trace_id=None,
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
            error_message = safe_error_type(e)
            logger.error("Query execution failed", error_type=error_message)
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
            error_message = safe_error_type(e)
            logger.error("Modify execution failed", error_type=error_message)
            raise
        finally:
            execution_time = (ambient_clock.timestamp()) - start_time
            await self._log_query(sql, params, execution_time, success, error_message)
