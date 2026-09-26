"""Query execution mixin for DatabaseService."""

from __future__ import annotations

import time
from typing import Any, cast

from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    DuplicateKeyError,
    ForeignKeyError,
    QueryError,
)

logger = get_logger(__name__)


class _QueryMixin:
    """Mixin providing query execution methods for DatabaseService.

    All ``self.*`` attribute accesses here are satisfied by ``DatabaseService.__init__``
    or sibling mixins; ``# type: ignore[attr-defined]`` comments suppress mypy errors
    for attributes not declared on this mixin but guaranteed to exist at runtime.
    """

    async def execute_query(self, query: str, params: Any = None) -> QueryResult:
        """Execute a SQL query with optional parameters.

        Args:
            query: The SQL query string.
            params: Optional query parameters.

        Returns:
            QueryResult with rows, row_count, and execution metadata.
        """
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        start_counter = time.perf_counter()
        pipeline = self._ensure_resilience_pipeline()  # type: ignore[attr-defined]

        name = getattr(self.config, "name", "database")  # type: ignore[attr-defined]

        async def _record_metrics(
            p_name: str, duration_ms: float, error: bool = False
        ) -> None:
            metrics = getattr(self, "metrics", None)
            if not metrics:
                return
            histogram = getattr(metrics, "histogram", None)
            counter = getattr(metrics, "counter", None)
            if not callable(histogram) or not callable(counter):
                return
            try:
                await metrics.histogram("db.query.latency", duration_ms)
                await metrics.counter("db.query.count", 1)
                if error:
                    await metrics.counter("db.query.errors", 1)
            except Exception as e:
                logger.debug("metrics_recording_failed", error=str(e))

        try:
            if self.tracer:  # type: ignore[attr-defined]
                try:
                    with self.tracer.start_span(f"db.{name}"):  # type: ignore[attr-defined]
                        if pipeline:
                            res = await pipeline.execute(
                                lambda: self.db_provider.execute_query(query, params),  # type: ignore[attr-defined]
                            )
                        else:
                            res = await self.db_provider.execute_query(query, params)  # type: ignore[attr-defined]

                        duration = (time.perf_counter() - start_counter) * 1000
                        await _record_metrics(name, duration)
                        return self._to_query_result(res, duration)
                except (
                    DatabaseError,
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    QueryError,
                    OSError,
                    ConnectionError,
                    RuntimeError,
                    TimeoutError,
                ):
                    duration = (time.perf_counter() - start_counter) * 1000
                    await _record_metrics(name, duration, error=True)
                    raise

            if pipeline:
                res = await pipeline.execute(
                    lambda: self.db_provider.execute_query(query, params),  # type: ignore[attr-defined]
                )
            else:
                res = await self.db_provider.execute_query(query, params)  # type: ignore[attr-defined]

            duration = (time.perf_counter() - start_counter) * 1000
            await _record_metrics(name, duration)
            return self._to_query_result(res, duration)
        except (
            DatabaseError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            QueryError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
        ):
            if not self.tracer:  # type: ignore[attr-defined]
                duration = (time.perf_counter() - start_counter) * 1000
                await _record_metrics(name, duration, error=True)
            raise

    # ------------------------------------------------------------------
    # Internal normalisation helper — converts raw driver results to
    # the canonical QueryResult type.
    # ------------------------------------------------------------------

    @staticmethod
    def _to_query_result(raw: Any, execution_time: float) -> QueryResult:
        """Normalise a raw driver response into a QueryResult.

        Args:
            raw: The raw value returned by the underlying driver.
            execution_time: Query wall-clock time in milliseconds.

        Returns:
            A QueryResult wrapping the raw rows.
        """
        if isinstance(raw, QueryResult):
            return raw
        if isinstance(raw, list):
            rows = [dict(r) if not isinstance(r, dict) else r for r in raw]
            return QueryResult(
                rows=rows,
                row_count=len(rows),
                execution_time=execution_time,
                success=True,
            )
        if hasattr(raw, "rows"):
            rows = list(raw.rows or [])
            rows = [dict(r) if not isinstance(r, dict) else r for r in rows]
            return QueryResult(
                rows=rows,
                row_count=len(rows),
                execution_time=execution_time,
                success=True,
            )
        # Unknown result type — return an empty successful result rather than
        # hiding the unknown shape.
        return QueryResult(
            rows=[],
            row_count=0,
            execution_time=execution_time,
            success=True,
        )

    async def execute_insert(self, table: str, data: dict[str, Any]) -> InsertResult:
        """Insert a row into a table."""
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        try:
            return cast(
                "InsertResult",
                await self.db_provider.execute_insert(table, data),  # type: ignore[attr-defined]
            )
        except (QueryError, DatabaseError) as exc:
            if isinstance(
                exc,
                (
                    DatabaseConnectionError,
                    DatabaseTimeoutError,
                    DuplicateKeyError,
                    ForeignKeyError,
                ),
            ):
                raise
            return InsertResult(
                success=False,
                inserted_id=None,
                affected_rows=0,
                execution_time=0.0,
                error_message=str(exc),
            )

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        where: str,
        params: Any = None,
    ) -> UpdateResult:
        """Update rows in a table."""
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        try:
            return cast(
                "UpdateResult",
                await self.db_provider.execute_update(table, data, where, params),  # type: ignore[attr-defined]
            )
        except (QueryError, DatabaseError) as exc:
            if isinstance(exc, (DatabaseConnectionError, DatabaseTimeoutError)):
                raise
            return UpdateResult(
                success=False,
                affected_rows=0,
                execution_time=0.0,
                error_message=str(exc),
            )

    async def execute_delete(
        self, table: str, where: str, params: Any = None
    ) -> DeleteResult:
        """Delete rows from a table."""
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        try:
            return cast(
                "DeleteResult",
                await self.db_provider.execute_delete(table, where, params),  # type: ignore[attr-defined]
            )
        except (QueryError, DatabaseError) as exc:
            if isinstance(exc, (DatabaseConnectionError, DatabaseTimeoutError)):
                raise
            return DeleteResult(
                success=False,
                affected_rows=0,
                execution_time=0.0,
                error_message=str(exc),
            )

    async def execute(self, sql: str, params: Any = None) -> QueryResult:
        """Execute a raw SQL statement and return a structured QueryResult.

        Reads (``SELECT``/``PRAGMA``/``EXPLAIN``/``WITH``/anything with
        ``RETURNING``) delegate to :meth:`execute_query`. Writes are routed
        through the driver's dispatching ``execute`` so DML is **committed**
        — previously every statement went through the read path, which on
        SQLite left INSERT/UPDATE/DELETE in an open implicit transaction
        that was silently rolled back when the connection closed unless a
        later statement happened to commit it.

        Exceptions from the driver are caught and returned as a failed
        QueryResult so callers can inspect ``result.success`` instead of
        handling exceptions.

        Args:
            sql: The SQL statement string.
            params: Optional query parameters.

        Returns:
            QueryResult with rows, row_count, execution_time and success flag.
        """
        sql_upper = sql.strip().upper() if isinstance(sql, str) else ""
        is_read = (
            sql_upper.startswith(("SELECT", "PRAGMA", "EXPLAIN", "WITH", "SHOW"))
            or "RETURNING" in sql_upper
        )
        try:
            if is_read:
                return await self.execute_query(sql, params)
            return await self._execute_write(sql, params)
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as exc:
            return QueryResult(
                rows=[],
                row_count=0,
                execution_time=0.0,
                success=False,
                error_message=str(exc),
            )

    async def _execute_write(self, sql: str, params: Any = None) -> QueryResult:
        """Execute a mutating statement via the driver's committing path.

        Mirrors :meth:`execute_query`'s resilience/metrics handling but
        delegates to ``db_provider.execute``, whose CRUD dispatcher commits
        DML (and creates/commits DDL) instead of treating it as a SELECT.

        Args:
            sql: The SQL statement string.
            params: Optional query parameters.

        Returns:
            QueryResult normalised from the driver response.
        """
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        start_counter = time.perf_counter()
        pipeline = self._ensure_resilience_pipeline()  # type: ignore[attr-defined]

        if pipeline:
            res = await pipeline.execute(
                lambda: self.db_provider.execute(sql, params),  # type: ignore[attr-defined]
            )
        else:
            res = await self.db_provider.execute(sql, params)  # type: ignore[attr-defined]

        duration = (time.perf_counter() - start_counter) * 1000
        metrics = getattr(self, "metrics", None)
        if metrics:
            histogram = getattr(metrics, "histogram", None)
            counter = getattr(metrics, "counter", None)
            if callable(histogram) and callable(counter):
                try:
                    await metrics.histogram("db.query.latency", duration)
                    await metrics.counter("db.query.count", 1)
                except Exception as e:  # noqa: BLE001 — metrics must never break queries
                    logger.debug("metrics_recording_failed", error=str(e))
        return self._to_query_result(res, duration)
