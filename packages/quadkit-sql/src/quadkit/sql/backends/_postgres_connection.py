"""PostgresConnection implementation for PostgreSQL driver."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from quadkit.logging import get_logger
from quadkit.sql.abstractions.connection import DatabaseConnection
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

logger = get_logger(__name__)

asyncpg: Any
try:
    import asyncpg as _asyncpg

    asyncpg = _asyncpg
except ImportError:
    asyncpg = None

PostgresError: Any = getattr(asyncpg, "PostgresError", Exception)

# Monitoring type - try to import real monitor, otherwise provide fallback
HAS_MONITORING: bool
DatabaseMonitor: Any
try:
    from quadkit.sql.monitoring import DatabaseMonitor as _RealDatabaseMonitor

    DatabaseMonitor = _RealDatabaseMonitor
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False

    class _FallbackDatabaseMonitor:
        def get_query_monitor(self) -> Any:
            class _Dummy:
                @asynccontextmanager
                async def monitor_query(
                    self,
                    *args: Any,
                    **kwargs: Any,
                ) -> AsyncGenerator[None, None]:
                    yield

            return _Dummy()

    DatabaseMonitor = _FallbackDatabaseMonitor


__all__ = ["PostgresConnection"]


class PostgresConnection(DatabaseConnection):
    """PostgreSQL database connection"""

    def __init__(self, connection: Any, monitor: Any | None = None) -> None:
        self._conn = connection
        self.monitor = monitor
        self.connection_id = f"postgres_{id(connection)}"

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
                        result = await self._conn.execute(query, *params)
                    else:
                        result = await self._conn.execute(query)
                    return result
                except PostgresError as e:
                    logger.exception("Postgres query execution failed")
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
                    logger.exception("Postgres query execution failed (unexpected)")
                    raise DatabaseConnectionError(
                        f"Connection error during execute: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
        else:
            try:
                if params:
                    result = await self._conn.execute(query, *params)
                else:
                    result = await self._conn.execute(query)
                return result
            except PostgresError as e:
                logger.exception("Postgres query execution failed")
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
                logger.exception("Postgres query execution failed (unexpected)")
                raise DatabaseConnectionError(
                    f"Connection error during execute: {e}",
                    details={"query": query, "error": str(e)},
                ) from e

    async def execute_many(
        self,
        query: str,
        params_list: list[tuple[object, ...]],
    ) -> None:
        """Execute a query with multiple parameter sets"""
        try:
            async with self._conn.transaction():
                for params in params_list:
                    await self._conn.execute(query, *params)
        except PostgresError as e:
            logger.exception("Postgres batch execution failed")
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
            logger.exception("Unexpected error in Postgres batch operation")
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
                    if params:
                        row = await self._conn.fetchrow(query, *params)
                    else:
                        row = await self._conn.fetchrow(query)

                    if row:
                        # Convert Record to dict
                        return dict(row)
                    return None
                except PostgresError as e:
                    logger.exception("Postgres query fetch failed")
                    raise QueryError(
                        f"Query fetch failed: {e}",
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    Exception,
                ) as e:
                    logger.exception("Postgres query fetch failed (unexpected)")
                    raise QueryError(f"Unexpected Postgres error: {e}") from e
        else:
            try:
                if params:
                    row = await self._conn.fetchrow(query, *params)
                else:
                    row = await self._conn.fetchrow(query)

                if row:
                    # Convert Record to dict
                    return dict(row)
                return None
            except PostgresError as e:
                logger.exception("Postgres query fetch failed")
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
                logger.exception("Postgres query fetch failed (unexpected)")
                raise QueryError(f"Unexpected Postgres error: {e}") from e

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
                    if params:
                        rows = await self._conn.fetch(query, *params)
                    else:
                        rows = await self._conn.fetch(query)

                    # Convert Records to dicts
                    return list(map(dict, rows))
                except PostgresError as e:
                    logger.exception("Postgres query fetch all failed")
                    raise QueryError(
                        f"Query fetch all failed: {e}",
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    Exception,
                ) as e:
                    logger.exception("Unexpected error in Postgres fetch all operation")
                    raise QueryError(
                        f"Query fetch all failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
        else:
            try:
                if params:
                    rows = await self._conn.fetch(query, *params)
                else:
                    rows = await self._conn.fetch(query)

                # Convert Records to dicts
                return list(map(dict, rows))
            except PostgresError as e:
                logger.exception("Postgres query fetch all failed")
                raise QueryError(
                    f"Query fetch all failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                Exception,
            ) as e:
                logger.exception("Unexpected error in Postgres fetch all operation")
                raise QueryError(
                    f"Query fetch all failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e

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
            logger.exception("Failed to close Postgres connection")

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[PostgresConnection, None]:
        """Simple transaction context manager for Postgres connection"""
        try:
            yield self
        finally:
            pass
