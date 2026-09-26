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
    TransactionMetrics,
)

logger = get_logger(__name__)


class TransactionMonitor:
    """Monitors database transaction execution"""

    def __init__(
        self,
        collector: DbMetricsCollector,
    ):
        self.collector = collector

    def _get_datetime(self) -> datetime:
        """Get current datetime."""
        return ambient_clock.now()

    @asynccontextmanager
    async def monitor_transaction(
        self,
        transaction_id: str,
        nested_level: int = 0,
    ) -> AsyncGenerator[None, None]:
        """Context manager to monitor transaction execution"""
        start_time = self._get_datetime()
        success = False
        operation = "unknown"
        deadlock_detected = False
        error_message = None

        try:
            yield
            success = True
            operation = "commit"
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
            operation = "rollback"

            # Check for deadlock indicators
            error_lower = error_message.lower()
            if any(
                keyword in error_lower
                for keyword in [
                    "deadlock",
                    "lock wait timeout",
                    "serialization failure",
                ]
            ):
                deadlock_detected = True

            raise
        finally:
            end_time = self._get_datetime()
            duration = (end_time - start_time).total_seconds()

            metrics = TransactionMetrics(
                transaction_id=transaction_id,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                operation=operation,
                success=success,
                deadlock_detected=deadlock_detected,
                error_message=error_message,
                nested_level=nested_level,
            )

            await self.collector.record_transaction_metrics(metrics)

    async def get_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get transaction monitoring statistics"""
        return await self.collector.get_transaction_stats(time_range_seconds)
