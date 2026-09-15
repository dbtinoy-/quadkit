"""Database query logging contracts (renamed from ``logging.py``).

This module contains the contracts for database query logging.  It was
created during the 2026 reorganization when the previous
``data/logging.py`` module was renamed; the old path is no longer supported.
Consumers should import directly from ``quadkit.contracts.data``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class QueryLogEntry:
    """Represents a database query log entry.

    This is a concrete dataclass rather than a Protocol so that
    callers can instantiate it directly.
    """

    sql: str
    params: tuple[Any, ...] | None = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error_message: str | None = None
    connection_id: str | None = None
    transaction_id: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None


@runtime_checkable
class QueryLoggerProtocol(Protocol):
    """Protocol for logging database queries.

    Implement this protocol to enable query logging in database providers.
    The concrete :class:`quadkit.sql.logging.BaseQueryLogger` implements
    this interface and adds helper methods for querying the stored entries.
    """

    async def log_query(
        self,
        entry: QueryLogEntry,
    ) -> None:  # pragma: no cover - protocol
        """Log a query execution."""
        ...

    async def get_recent_queries(self, limit: int = 100) -> list[QueryLogEntry]:
        """Return the most recent ``limit`` entries."""
        ...

    async def get_slow_queries(
        self,
        threshold_seconds: float,
        limit: int = 50,
    ) -> list[QueryLogEntry]:
        """Return entries whose execution time exceeds ``threshold_seconds``."""
        ...

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Return aggregated statistics over a time window."""
        ...


__all__ = [
    "QueryLogEntry",
    "QueryLoggerProtocol",
]
