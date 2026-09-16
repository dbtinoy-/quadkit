"""Time-series database protocols for event and metric storage.

Provides driver-agnostic abstractions for time-series stores
(TimescaleDB, InfluxDB, etc.) supporting continuous event insertion
and windowed querying.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.health import HealthCheckResult


@runtime_checkable
class TimeSeriesStoreProtocol(Protocol):
    """Protocol for a time-series database provider.

    Provides continuous data stream ingestion, windowed queries, and
    lifecycle management.
    """

    async def connect(self) -> None:
        """Establish connection to the time-series store."""
        ...

    async def disconnect(self) -> None:
        """Close all connections."""
        ...

    def is_connected(self) -> bool:
        """Check if the store is connected."""
        ...

    async def insert(self, series: str, data: list[dict[str, Any]]) -> None:
        """Insert sequence data points into a specific series/measurement.

        Args:
            series: The series, measurement, or bucket name.
            data: Data points, typically including a timestamp and values.
        """
        ...

    async def query(
        self,
        series: str,
        start_time: Any,
        end_time: Any,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query data points within a time window.

        Args:
            series: The series name to query.
            start_time: Timestamp representing the beginning of the window.
            end_time: Timestamp representing the end of the window.
            filter: Optional tags/metadata to filter on.

        Returns:
            List of matched data point dicts.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check time-series store connectivity and health."""
        ...


__all__ = [
    "TimeSeriesStoreProtocol",
]
