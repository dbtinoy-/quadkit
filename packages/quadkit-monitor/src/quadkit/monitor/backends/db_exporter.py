"""Database-backed MetricsExporter implementation

Writes metric observations into a database table suitable for later analysis.
This exporter depends on a DatabaseService (`quadkit.sql.providers.database_provider.DatabaseService`)
exposing `execute_query(sql, params=None)`.
"""

from __future__ import annotations

from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


class DBMetricsExporter:
    """Exporter that persists metric samples to a database table.

    Writes every metric observation (counter, gauge, histogram) as a row in
    *table*.  The table must have the schema::

        CREATE TABLE metrics_samples (
            name        TEXT    NOT NULL,
            metric_type TEXT    NOT NULL,   -- 'counter' | 'gauge' | 'histogram'
            labels      JSONB,
            value       DOUBLE PRECISION NOT NULL,
            recorded_at TIMESTAMPTZ DEFAULT now()
        );

    The exporter is configured via the
    :class:`~quadkit.monitor.config.MonitoringConfig` ``store_in_db`` flag and
    wired automatically by
    :class:`~quadkit.monitor.di.provider.MonitorProvider` when a
    :class:`~quadkit.contracts.data.DatabaseProviderProtocol` binding is
    present in the container.

    Args:
        db_provider: A database provider that exposes an
            ``execute_query(sql, params)`` coroutine.  Typically a
            :class:`~quadkit.sql.providers.database_provider.DatabaseService`
            instance resolved through constructor injection.
        table: Name of the target table.  Defaults to ``"metrics_samples"``.

    Example::

        exporter = DBMetricsExporter(db_provider=my_db)
        await exporter.counter("api.requests", 1, {"endpoint": "/users"})
        await exporter.histogram("db.query_ms", 12.4, {"table": "users"})
    """

    def __init__(self, db_provider: Any, table: str = "metrics_samples") -> None:
        self._db = db_provider
        self._table = table

    async def counter(self, name: str, value: int, tags: dict[str, str]) -> None:
        """Record a counter metric observation.

        Args:
            name: MetricProtocol name, e.g. ``"api.requests"``.
            value: Non-negative integer increment.
            tags: Arbitrary string key-value labels stored as JSON.
        """
        await self._insert(name, "counter", value, tags)

    async def gauge(self, name: str, value: float, tags: dict[str, str]) -> None:
        """Record a gauge metric observation.

        Args:
            name: MetricProtocol name, e.g. ``"worker.queue_depth"``.
            value: Current gauge reading (signed float).
            tags: Arbitrary string key-value labels stored as JSON.
        """
        await self._insert(name, "gauge", value, tags)

    async def histogram(self, name: str, value: float, tags: dict[str, str]) -> None:
        """Record a histogram sample.

        Args:
            name: MetricProtocol name, e.g. ``"http.request.duration"``.
            value: Observed measurement (e.g. duration in seconds).
            tags: Arbitrary string key-value labels stored as JSON.
        """
        await self._insert(name, "histogram", value, tags)

    async def flush(self) -> None:
        """Flush buffered observations to the database.

        This exporter writes directly on every observation, so flush is a
        no-op.  The method exists to satisfy the exporter protocol contract.
        """
        # Nothing special to flush when writing directly to DB

    async def _insert(
        self,
        name: str,
        metric_type: str,
        value: float,
        labels: dict[str, Any] | None,
    ) -> None:
        try:
            # Use JSON-compatible labels insertion if supported; provider handles paramization
            sql = f"INSERT INTO {self._table} (name, metric_type, labels, value) VALUES ($1, $2, $3, $4)"  # noqa: S608 -- init-time config attribute, never user input
            from quadkit import serialization as json

            labels_payload = json.dumps(labels or {})
            params = [name, metric_type, labels_payload, float(value)]
            await self._db.execute_query(sql, params)
        except Exception:  # pragma: no cover - defensive # noqa: BLE001 — metric export must never raise into the app
            logger.exception("Failed to write metric to DB")
