"""QueryEngine implementation for quadkit-sql."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.sql.database import QueryResult
from quadkit.di.decorators import inject

if TYPE_CHECKING:
    from quadkit.sql.api.protocols import DatabaseProviderProtocol


@inject
class QueryEngine:
    """Convenience wrapper for raw SQL queries via DatabaseService.

    This is a concrete implementation, not a protocol.
    Inject ``DatabaseProviderProtocol`` directly for more control.

    Prefers the provider's ``execute_query()`` method (the canonical
    ``DatabaseService`` path) so backends such as aiosqlite / asyncpg are
    normalised through :class:`QueryResult`.  When the provider only exposes
    a raw ``get_connection()``/``execute()`` API, results are normalised from
    the driver's ``fetch_all`` / ``fetchall`` interface so tuple-based rows
    (SQLite, asyncpg, MySQL) still return dict rows and scalar values.
    """

    def __init__(self, provider: DatabaseProviderProtocol):
        self.provider = provider

    @staticmethod
    def _normalise_rows(description: Any, rows: Any) -> list[dict[str, Any]]:
        """Normalise tuple rows into dict rows using cursor column names."""
        if not rows:
            return []
        if all(isinstance(r, dict) for r in rows):
            return list(rows)

        columns = (
            [col[0] for col in description]
            if description and not callable(description)
            else []
        )
        if not columns:
            width = len(rows[0]) if isinstance(rows[0], (tuple, list)) else 1
            columns = [f"col_{i}" for i in range(width)]
        return [
            dict(
                zip(
                    columns,
                    list(row) if isinstance(row, (tuple, list)) else [row],
                    strict=False,
                )
            )
            for row in rows
        ]

    @staticmethod
    async def _rows_from_result(result: Any) -> list[dict[str, Any]]:
        """Return ``list[dict]`` rows from a structured or raw driver result.

        Handles both :class:`QueryResult` and the raw shapes returned by
        ``aiosqlite`` / ``asyncpg`` / ``aiomysql`` (tuple rows,
        ``description`` metadata, or already-dict rows).
        """
        if isinstance(result, QueryResult):
            return list(result.rows or [])

        rows = getattr(result, "rows", None)
        if rows is not None and not callable(rows):
            return QueryEngine._normalise_rows(
                getattr(result, "description", None), rows
            )

        fetchall = getattr(result, "fetchall", None)
        if callable(fetchall):
            fetched = fetchall()
            if hasattr(fetched, "__await__"):
                fetched = await fetched
            return QueryEngine._normalise_rows(
                getattr(result, "description", None), fetched
            )

        if isinstance(result, list):
            return QueryEngine._normalise_rows(None, result)

        return []

    async def _query_rows(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a query and return normalised dict rows."""
        execute_query = getattr(self.provider, "execute_query", None)
        if callable(execute_query):
            result = await execute_query(sql, params)
            return await self._rows_from_result(result)

        async with self.provider.get_connection() as conn:
            # Canonical DatabaseConnection API returns dict rows already.
            fetch_all = getattr(conn, "fetch_all", None)
            if callable(fetch_all):
                rows = await fetch_all(sql, params)
                return self._normalise_rows(None, rows)

            result = await conn.execute(sql, params)
            return await self._rows_from_result(result)

    async def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
        fetch: bool = True,
    ) -> Any:
        if fetch:
            return await self._query_rows(sql, params)

        # Legacy non-fetch path: expose the raw driver result object.  For
        # providers with the structured execute_query API this is a
        # QueryResult; otherwise it is the raw cursor created by the driver.
        execute_query = getattr(self.provider, "execute_query", None)
        if callable(execute_query):
            return await execute_query(sql, params)

        async with self.provider.get_connection() as conn:
            return await conn.execute(sql, params)

    async def fetchone(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> dict[str, Any] | None:
        rows = await self._query_rows(sql, params)
        return rows[0] if rows else None

    async def fetchall(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[dict[str, Any]]:
        return await self._query_rows(sql, params)

    async def scalar(self, sql: str, params: tuple[object, ...] | None = None) -> Any:
        rows = await self._query_rows(sql, params)
        if not rows:
            return None
        first = rows[0]
        # Rows are always dicts (normalised by ``_query_rows``); prefer the
        # conventional "count" key, otherwise the first column value.
        return first.get("count", next(iter(first.values())))


__all__ = ["QueryEngine"]
