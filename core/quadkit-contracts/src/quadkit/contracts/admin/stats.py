"""Runtime capability protocols for admin dashboard data sources.

These protocols are checked with ``isinstance`` (hence ``runtime_checkable``)
so that widget handlers can consume real data from *any* injected object
that structurally implements them, without forcing every implementation
of the narrower core protocols to gain new methods.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SessionCountProtocol(Protocol):
    """Capability: count currently active sessions."""

    async def count_active(self, cutoff: Any) -> int:
        """Return count of sessions expiring after ``cutoff``."""
        ...


@runtime_checkable
class CacheStatsProtocol(Protocol):
    """Capability: cache backend hit/miss/eviction statistics.

    ``get_stats()`` returns a dict with the keys ``hits``, ``misses``,
    ``evictions``, ``entries`` (each ``int``) or ``None`` when stats are
    unavailable.
    """

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return backend statistics or ``None``."""
        ...


@runtime_checkable
class QueueStatsProtocol(Protocol):
    """Capability: queue depth/lag statistics.

    Returns a dict with keys ``pending`` and ``processing`` (``int``),
    or ``None``.
    """

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return queue statistics or ``None``."""
        ...


@runtime_checkable
class DlqStatsProtocol(Protocol):
    """Capability: dead-letter store statistics.

    Returns a dict with the key ``dead_letter_count`` (``int``), or ``None``.
    """

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return dead-letter statistics or ``None``."""
        ...


@runtime_checkable
class MetricsReadbackProtocol(Protocol):
    """Capability: read back registered metrics by name."""

    def get_metric(self, name: str) -> Any | None:
        """Return the metric object for ``name`` or ``None``."""
        ...

    def get_all_metrics(self) -> dict[str, Any]:
        """Return all registered metrics keyed by name."""
        ...


@runtime_checkable
class HealthOverviewProtocol(Protocol):
    """Capability: compute overall framework health."""

    async def run_all(self) -> tuple[Any, dict[str, Any]]:
        """Return ``(status_payload, details_dict)`` for all checks."""
        ...


@runtime_checkable
class NamedHealthCheckProtocol(Protocol):
    """Capability: run a single named health check."""

    async def run_check(self, name: str) -> dict[str, Any]:
        """Return the raw result dict for the named check."""
        ...


__all__ = [
    "CacheStatsProtocol",
    "DlqStatsProtocol",
    "HealthOverviewProtocol",
    "MetricsReadbackProtocol",
    "NamedHealthCheckProtocol",
    "QueueStatsProtocol",
    "SessionCountProtocol",
]
