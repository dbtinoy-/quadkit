"""Buffered metric recording with configurable flush intervals.

Allows high-throughput code to record metrics without per-record overhead
by accumulating entries in memory and flushing in batches.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class BufferedMetricEntry:
    """A single buffered metric recording.

    Attributes:
        name: MetricProtocol name.
        value: Numeric value to record.
        labels: Optional label key-value pairs.
        timestamp: Monotonic timestamp when the entry was created.
    """

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


class BufferedMetricRecorder:
    """Buffers metric recordings and flushes them in configurable batches.

    Reduces metric backend overhead for high-throughput code paths by
    accumulating entries and flushing at intervals or when the buffer is full.

    Args:
        backend: MetricProtocol backend instance with metric attributes exposing ``record()``.
        flush_interval: Seconds between automatic periodic flushes. Default: 5.0.
        max_buffer_size: Maximum entries before a forced flush. Default: 1000.

    Example::

        recorder = BufferedMetricRecorder(backend=monitor_backend, flush_interval=2.0)
        await recorder.start()

        recorder.record("request_count", 1.0, {"method": "GET"})
        # ... many more records ...

        await recorder.stop()  # flushes remaining entries
    """

    def __init__(
        self,
        backend: Any,
        flush_interval: float = 5.0,
        max_buffer_size: int = 1000,
    ) -> None:
        self._backend = backend
        self._flush_interval = flush_interval
        self._max_buffer_size = max_buffer_size
        self._buffer: list[BufferedMetricEntry] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def record(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Buffer a metric entry for deferred recording.

        If the buffer reaches max_buffer_size, schedules an immediate flush.

        Args:
            name: MetricProtocol name (must match an attribute on the backend).
            value: Numeric value to record.
            labels: Optional label key-value pairs.
        """
        self._buffer.append(
            BufferedMetricEntry(name=name, value=value, labels=labels or {})
        )
        if len(self._buffer) >= self._max_buffer_size:
            create_tracked_task(
                self.flush(),
                self._background_tasks,
                name=f"metrics_flush_buffer_{id(self)}",
            )

    async def flush(self) -> int:
        """Flush all buffered entries to the backend.

        Returns:
            Number of entries successfully flushed.
        """
        if not self._buffer:
            return 0
        batch, self._buffer = self._buffer, []
        count = 0
        for entry in batch:
            try:
                metric = getattr(self._backend, entry.name, None)
                if metric is not None and hasattr(metric, "record"):
                    await metric.record(entry.value, entry.labels)
                    count += 1
                else:
                    logger.debug("buffered_metric_skipped", name=entry.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "buffered_metric_flush_error", name=entry.name, error=str(exc)
                )
        if count:
            logger.debug("buffered_metrics_flushed", count=count)
        return count

    async def start(self) -> None:
        """Start the periodic background flush task."""
        create_tracked_task(
            self._periodic_flush(),
            self._background_tasks,
            name=f"metrics_flush_periodic_{id(self)}",
        )

    async def stop(self) -> None:
        """Stop the background flush task and flush remaining entries."""
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        await self.flush()

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush()


__all__ = ["BufferedMetricEntry", "BufferedMetricRecorder"]
