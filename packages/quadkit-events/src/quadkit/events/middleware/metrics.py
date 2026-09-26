"""Metrics middleware for CQRS buses.

Provides execution metrics collection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any

from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler

if TYPE_CHECKING:
    from datetime import datetime

    from quadkit.contracts.observability.metrics import MetricsRecorderProtocol


@dataclass
class MessageMetrics:
    """Metrics for a single message execution."""

    message_type: str
    started_at: datetime
    duration_seconds: float
    success: bool
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that collects execution metrics.

    Tracks:
    - Execution count per message type
    - Success/failure rates
    - Execution duration histograms
    - Active executions gauge
    """

    def __init__(
        self,
        recorder: MetricsRecorderProtocol | None = None,
        metric_prefix: str = "cqrs",
    ):
        """Initialize the metrics middleware.

        Args:
            recorder: Metrics recorder
            metric_prefix: Prefix for metric names
        """
        self._recorder = recorder
        self._prefix = metric_prefix
        self._active_count = 0

    @property
    def recorder(self) -> MetricsRecorderProtocol | None:
        """Get the metrics recorder."""
        return self._recorder

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with metrics collection."""
        if self._recorder is None:
            return await next_handler(message)

        message_type = type(message).__name__
        tags = {"message_type": message_type}

        # Increment active count
        self._active_count += 1
        self._recorder.gauge(
            f"{self._prefix}.active_executions",
            float(self._active_count),
        )

        start_time = time.perf_counter()

        try:
            result = await next_handler(message)
            duration = time.perf_counter() - start_time

            # Record success metrics
            self._recorder.increment(
                f"{self._prefix}.executions",
                tags={**tags, "status": "success"},
            )
            self._recorder.histogram(
                f"{self._prefix}.duration_seconds",
                duration,
                tags=tags,
            )

            return result

        except Exception as e:  # noqa: BLE001 — middleware observation; records duration metrics and re-raises
            duration = time.perf_counter() - start_time

            # Record failure metrics
            self._recorder.increment(
                f"{self._prefix}.executions",
                tags={**tags, "status": "error", "error_type": type(e).__name__},
            )
            self._recorder.histogram(
                f"{self._prefix}.duration_seconds",
                duration,
                tags=tags,
            )

            raise

        finally:
            # Decrement active count
            self._active_count -= 1
            self._recorder.gauge(
                f"{self._prefix}.active_executions",
                float(self._active_count),
            )


__all__ = [
    "MessageMetrics",
    "MetricsMiddleware",
]
