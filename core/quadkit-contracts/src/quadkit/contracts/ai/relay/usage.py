"""Usage and rankings read contracts for the relay gateway.

The usage service aggregates persisted request logs into daily per-token
usage and per-model rankings.  Value types are frozen so they can cross
package boundaries safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.ai.relay.logs import RelayRequestLogEntry


@dataclass(frozen=True, slots=True)
class RelayDailyUsage:
    """One day of token/cost usage for a user."""

    day: str  # ISO date (YYYY-MM-DD) as stored by the aggregate
    prompt_tokens: int
    completion_tokens: int
    cost: str  # Decimal string


@dataclass(frozen=True, slots=True)
class RelayModelRank:
    """Aggregate usage for one model over a window.

    ``completion_tokens`` remains the original ranking measure used by
    existing admin consumers.  The prompt and total fields make the same
    contract useful for public usage leaderboards without forcing each app
    to re-query raw request logs or guess at token totals.
    """

    model: str
    completion_tokens: int
    request_count: int
    cost: str  # Decimal string
    prompt_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class RelayModelRankBucket:
    """One model's token usage in a fixed UTC history bucket.

    ``bucket_start`` is the inclusive start of the bucket.  The value is
    intentionally a datetime rather than a presentation label so consumers
    can choose locale-aware formatting without re-querying the log store.
    ``model_rank_history`` orders rows by bucket start and then total usage.
    """

    bucket_start: datetime
    model: str
    completion_tokens: int
    request_count: int
    cost: str  # Decimal string
    prompt_tokens: int = 0
    total_tokens: int = 0


@runtime_checkable
class RelayUsageServiceProtocol(Protocol):
    """Read model over persisted relay request logs.

    Both methods are best-effort reads over the durable store; query
    failures surface as warnings, not request-path failures.
    """

    async def daily_usage(self, user_id: str, days: int) -> list[RelayDailyUsage]: ...

    async def model_rank(self, days: int, limit: int) -> list[RelayModelRank]: ...

    async def model_rank_window(
        self,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[RelayModelRank]:
        """Rank models inside an explicit closed time window.

        Args:
            start: Inclusive UTC window start.
            end: Inclusive UTC window end.
            limit: Maximum number of rows to return.

        Returns:
            Models ordered by total token usage descending.  Implementations
            may retain the legacy completion-token ordering when total usage
            is unavailable, but must populate ``total_tokens`` when possible.
        """
        ...

    async def model_rank_history(
        self,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
        limit: int,
    ) -> list[RelayModelRankBucket]:
        """Return per-model usage grouped into fixed UTC history buckets.

        Args:
            start: Inclusive UTC history window start.
            end: Inclusive UTC history window end.
            bucket_seconds: Positive bucket width in seconds.
            limit: Maximum number of models returned per bucket.

        Returns:
            Rows ordered by bucket start, then descending total tokens. Empty
            buckets are omitted; callers can derive the displayed bucket count
            from the returned ``bucket_start`` values.
        """
        ...

    async def list_requests(
        self,
        days: int,
        page: int,
        page_size: int,
        *,
        user_id: str | None = None,
        token_id: str | None = None,
    ) -> list[RelayRequestLogEntry]:
        """List recent request-log entries, newest first."""
        ...


__all__ = [
    "RelayDailyUsage",
    "RelayModelRank",
    "RelayModelRankBucket",
    "RelayUsageServiceProtocol",
]
