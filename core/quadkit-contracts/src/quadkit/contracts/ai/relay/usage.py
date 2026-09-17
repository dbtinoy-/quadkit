"""Usage and rankings read contracts for the relay gateway.

The usage service aggregates persisted request logs into daily per-token
usage and per-model rankings.  Value types are frozen so they can cross
package boundaries safely.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """Aggregate usage for one model over a window."""

    model: str
    completion_tokens: int
    request_count: int
    cost: str  # Decimal string


@runtime_checkable
class RelayUsageServiceProtocol(Protocol):
    """Read model over persisted relay request logs.

    Both methods are best-effort reads over the durable store; query
    failures surface as warnings, not request-path failures.
    """

    async def daily_usage(self, user_id: str, days: int) -> list[RelayDailyUsage]: ...

    async def model_rank(self, days: int, limit: int) -> list[RelayModelRank]: ...

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


__all__ = ["RelayDailyUsage", "RelayModelRank", "RelayUsageServiceProtocol"]
