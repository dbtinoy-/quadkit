"""MySQL database driver implementation"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from quadkit.logging import get_logger
from quadkit.sql.abstractions.connection import DatabaseConnection
from quadkit.sql.backends.mysql._shims import (
    MySQLError,
    aiomysql,
)
from quadkit.sql.monitoring import DatabaseMonitor

logger = get_logger(__name__)

HAS_MONITORING = True

from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)


class MySQLConnection(DatabaseConnection):
    """MySQL database connection"""

    def __init__(self, connection: Any, monitor: DatabaseMonitor | None = None) -> None:
        self._conn = connection
        self.monitor = monitor
        self.connection_id = f"mysql_{id(connection)}"

    async def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> Any:
        """Execute a query and return results"""
        if self.monitor and HAS_MONITORING:
            async with self.monitor.get_query_monitor().monitor_query(
                query=query,
                parameters=list(params) if params else None,
                connection_id=self.connection_id,
            ):
                try:
                    if params:
                        await self._conn.execute(query, params)
                    else:
                        await self._conn.execute(query)
                    return self._conn.affected_rows
                except MySQLError as e:  # type: ignore[misc]
                    logger.exception("MySQL query execution failed")
                    raise QueryError(
                        f"Query execution failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    Exception,
                ) as e:
                    logger.exception("MySQL query execution failed (unexpected)")
                    raise QueryError(
                        f"Query execution failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
        else:
            try:
                if params:
                    await self._conn.execute(query, params)
                else:
                    await self._conn.execute(query)
                return self._conn.affected_rows
            except MySQLError as e:  # type: ignore[misc]
                logger.exception("MySQL query execution failed")
                raise QueryError(
                    f"Query execution failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                Exception,
            ) as e:
                logger.exception("MySQL query execution failed (unexpected)")
                raise QueryError(
                    f"Query execution failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e

    async def execute_many(
        self,
        query: str,
        params_list: list[tuple[object, ...]],
    ) -> None:
        """Execute a query with multiple parameter sets"""
        try:
            async with self._conn.cursor() as cursor:
                await cursor.executemany(query, params_list)
                await self._conn.commit()
        except MySQLError as e:  # type: ignore[misc]
            logger.exception("MySQL batch execution failed")
            raise QueryError(
                f"Batch execution failed: {e}",
                details={"query": query, "error": str(e)},
            ) from e
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            Exception,
        ) as e:
            logger.exception("Unexpected error in MySQL batch operation")
            raise QueryError(
                f"Batch execution failed: {e}",
                details={"query": query, "error": str(e)},
            ) from e

    async def fetch_one(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a single row"""
        if self.monitor and HAS_MONITORING:
            async with self.monitor.get_query_monitor().monitor_query(
                query=query,
                parameters=list(params) if params else None,
                connection_id=self.connection_id,
            ):
                try:
                    async with self._conn.cursor(aiomysql.DictCursor) as cursor:
                        if params:
                            await cursor.execute(query, params)
                        else:
                            await cursor.execute(query)
                        result = await cursor.fetchone()
                        return cast("dict[str, Any] | None", result)
                except MySQLError as e:  # type: ignore[misc]  # type: ignore[misc]
                    logger.exception("MySQL query fetch failed")
                    raise QueryError(
                        f"Query fetch failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    Exception,
                ) as e:
                    logger.exception("Unexpected error in MySQL fetch operation")
                    raise QueryError(
                        f"Query fetch failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
        else:
            try:
                async with self._conn.cursor(aiomysql.DictCursor) as cursor:
                    if params:
                        await cursor.execute(query, params)
                    else:
                        await cursor.execute(query)
                    result = await cursor.fetchone()
                    return cast("dict[str, Any] | None", result)
            except MySQLError as e:  # type: ignore[misc]
                logger.exception("MySQL query fetch failed")
                raise QueryError(
                    f"Query fetch failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                Exception,
            ) as e:
                logger.exception("Unexpected error in MySQL fetch operation")
                raise QueryError(
                    f"Query fetch failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e

    async def fetch_all(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all rows"""
        if self.monitor and HAS_MONITORING:
            async with self.monitor.get_query_monitor().monitor_query(
                query=query,
                parameters=list(params) if params else None,
                connection_id=self.connection_id,
            ):
                try:
                    async with self._conn.cursor(aiomysql.DictCursor) as cursor:
                        if params:
                            await cursor.execute(query, params)
                        else:
                            await cursor.execute(query)
                        result = await cursor.fetchall()
                        return result or []
                except MySQLError as e:  # type: ignore[misc]  # type: ignore[misc]
                    logger.exception("MySQL query fetch all failed")
                    raise QueryError(
                        f"Query fetch all failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                ) as e:
                    logger.exception("Unexpected error in MySQL fetch all operation")
                    raise QueryError(
                        f"Query fetch all failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
        else:
            try:
                async with self._conn.cursor(aiomysql.DictCursor) as cursor:
                    if params:
                        await cursor.execute(query, params)
                    else:
                        await cursor.execute(query)
                    result = await cursor.fetchall()
                    return result or []
            except MySQLError as e:  # type: ignore[misc]
                logger.exception("MySQL query fetch all failed")
                raise QueryError(
                    f"Query fetch all failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
            ) as e:
                logger.exception("Unexpected error in MySQL fetch all operation")
                raise QueryError(
                    f"Query fetch all failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[MySQLConnection, None]:
        """Simple transaction context manager for MySQL connection"""
        try:
            yield self
        finally:
            pass

    async def close(self) -> None:
        """Close the connection"""
        try:
            if hasattr(self._conn, "close"):
                close_fn = self._conn.close
                if asyncio.iscoroutinefunction(close_fn):
                    await close_fn()
                else:
                    close_fn()
        except (
            OSError,
            ConnectionError,
            RuntimeError,
        ):  # pragma: no cover - best-effort close
            logger.exception("Failed to close MySQL connection")


# ...
