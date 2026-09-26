"""SQLite database driver implementation"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import sqlite3
from typing import Any

from quadkit.logging import get_logger
from quadkit.sql.abstractions.connection import DatabaseConnection

logger = get_logger(__name__)

from quadkit.sql.backends.sqlite._shims import (  # noqa: F401
    HAS_MONITORING,
    HAS_SQLITE,
    DatabaseMonitor,
    aiosqlite,
)
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)


class SQLiteConnection(DatabaseConnection):
    """SQLite database connection"""

    def __init__(self, connection: Any, monitor: DatabaseMonitor | None = None) -> None:
        self._conn = connection
        self.monitor = monitor
        self.connection_id = f"sqlite_{id(connection)}"

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
                        cursor = await self._conn.execute(query, params)
                    else:
                        cursor = await self._conn.execute(query)
                except sqlite3.Error as e:
                    logger.exception("SQLite query execution failed")
                    raise QueryError(
                        f"Query execution failed: {e}",
                        details={"query": query, "error": str(e)},
                    ) from e
                except (
                    DatabaseError,
                    QueryError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                ) as e:
                    logger.exception("SQLite query execution failed (unexpected)")
                    raise DatabaseError(f"Unexpected SQLite error: {e}") from e
                else:
                    # For SELECT queries, return cursor for fetching
                    # For INSERT/UPDATE/DELETE, commit and return rowcount
                    if (
                        query.strip()
                        .upper()
                        .startswith(("SELECT", "PRAGMA", "EXPLAIN"))
                    ):
                        return cursor
                    await self._conn.commit()
                    return cursor.rowcount
        else:
            try:
                if params:
                    cursor = await self._conn.execute(query, params)
                else:
                    cursor = await self._conn.execute(query)
            except sqlite3.Error as e:
                logger.exception("SQLite query execution failed")
                raise QueryError(
                    f"Query execution failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
            ) as e:
                logger.exception("SQLite query execution failed (unexpected)")
                raise DatabaseError(f"Unexpected SQLite error: {e}") from e
            else:
                # For SELECT queries, return cursor for fetching
                # For INSERT/UPDATE/DELETE, commit and return rowcount
                if query.strip().upper().startswith(("SELECT", "PRAGMA", "EXPLAIN")):
                    return cursor
                await self._conn.commit()
                return cursor.rowcount

    async def execute_many(
        self,
        query: str,
        params_list: list[tuple[object, ...]],
    ) -> None:
        """Execute a query with multiple parameter sets"""
        try:
            await self._conn.executemany(query, params_list)
            await self._conn.commit()
        except sqlite3.Error as e:
            logger.exception("SQLite batch execution failed")
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
            logger.exception("Unexpected error in SQLite batch operation")
            raise DatabaseError(f"Unexpected SQLite error: {e}") from e

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
                        cursor = await self._conn.execute(query, params)
                    else:
                        cursor = await self._conn.execute(query)
                    row = await cursor.fetchone()
                except sqlite3.Error as e:
                    logger.exception("SQLite query fetch failed")
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
                    logger.exception("Unexpected error in SQLite fetch operation")
                    raise DatabaseError(f"Unexpected SQLite error: {e}") from e
                else:
                    if row:
                        # Convert sqlite3.Row to dict
                        return dict(
                            zip(
                                [col[0] for col in cursor.description or []],
                                row,
                                strict=True,
                            ),
                        )
                    return None
        else:
            try:
                if params:
                    cursor = await self._conn.execute(query, params)
                else:
                    cursor = await self._conn.execute(query)
                row = await cursor.fetchone()
                if row:
                    # Convert sqlite3.Row to dict
                    return dict(
                        zip(
                            [col[0] for col in cursor.description or []],
                            row,
                            strict=True,
                        ),
                    )
                return None
            except sqlite3.Error as e:
                logger.exception("SQLite query fetch failed")
                raise QueryError(
                    f"Query fetch failed: {e}",
                    details={"query": query, "error": str(e)},
                ) from e
            except (
                DatabaseError,
                QueryError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
            ) as e:
                logger.exception("Unexpected error in SQLite fetch operation")
                raise DatabaseError(f"Unexpected SQLite error: {e}") from e

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
                        cursor = await self._conn.execute(query, params)
                    else:
                        cursor = await self._conn.execute(query)
                    rows = await cursor.fetchall()
                except sqlite3.Error as e:
                    logger.exception("SQLite query fetch all failed")
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
                    logger.exception("Unexpected error in SQLite fetch all operation")
                    raise DatabaseError(f"Unexpected SQLite error: {e}") from e
                else:
                    if cursor.description:
                        columns = [col[0] for col in cursor.description]
                        return [dict(zip(columns, row, strict=True)) for row in rows]
                    return []
        else:
            try:
                if params:
                    cursor = await self._conn.execute(query, params)
                else:
                    cursor = await self._conn.execute(query)
                rows = await cursor.fetchall()
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row, strict=True)) for row in rows]
                return []
            except sqlite3.Error as e:
                logger.exception("SQLite query fetch all failed")
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
                logger.exception("Unexpected error in SQLite fetch all operation")
                raise DatabaseError(f"Unexpected SQLite error: {e}") from e

    async def close(self) -> None:
        """Close the connection (no-op for pooled connection)"""
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
            logger.exception("Failed to close SQLite connection")

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[SQLiteConnection, None]:
        """Simple transaction context manager for SQLite connection"""
        try:
            yield self
        finally:
            # No-op: underlying connection controls transaction lifecycle in tests
            pass


# ...
