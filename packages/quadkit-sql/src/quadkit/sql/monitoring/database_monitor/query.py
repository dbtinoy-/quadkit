"""Database monitoring classes"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.monitoring.metrics import (
    DbMetricsCollector,
    QueryMetrics,
)

logger = get_logger(__name__)


class QueryMonitor:
    """Monitors database query execution"""

    def __init__(
        self,
        collector: DbMetricsCollector,
        slow_query_threshold: float = 1.0,
    ):
        self.collector = collector
        self.slow_query_threshold = slow_query_threshold

    def _get_time(self) -> float:
        """Get current timestamp."""
        return ambient_clock.timestamp()

    def _get_datetime(self) -> datetime:
        """Get current datetime."""
        return ambient_clock.now()

    @asynccontextmanager
    async def monitor_query(
        self,
        query: str,
        parameters: list[Any] | None = None,
        connection_id: str | None = None,
        transaction_id: str | None = None,
    ) -> AsyncGenerator[None, None]:
        """Context manager to monitor query execution"""
        start_time = self._get_time()
        success = False
        error_message = None

        try:
            yield
            success = True
        except (
            DatabaseError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
            ValueError,
            TypeError,
        ) as e:
            error_message = str(e)
            raise
        finally:
            execution_time = self._get_time() - start_time

            metrics = QueryMetrics(
                query=query,
                parameters=parameters,
                execution_time=execution_time,
                timestamp=self._get_datetime(),
                success=success,
                error_message=error_message,
                connection_id=connection_id,
                transaction_id=transaction_id,
            )

            await self.collector.record_query_metrics(metrics)

            # Log slow queries
            if execution_time > self.slow_query_threshold:
                logger.warning("SLOW QUERY: %.3fs - %s", execution_time, query)

    async def get_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get monitoring statistics"""
        return await self.collector.get_query_stats(time_range_seconds)
