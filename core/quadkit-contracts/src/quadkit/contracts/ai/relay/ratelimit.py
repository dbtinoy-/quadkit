"""Rate-limit contracts for the relay gateway.

A counter is a fixed-window atomic ``take`` matched to new-api's Redis
Lua semantics: the counter is incremented, the window expiry is set on
first increment, and the decision is returned atomically.  Bursts of up
to 2x the limit at a window boundary are intentional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RelayRateLimitDecision:
    """Outcome of one ``take`` against a rate-limit window.

    Attributes:
        allowed: Whether the caller may proceed within the window.
        count: The counter value after this take, 1-based.
        ttl_seconds: Remaining seconds in the window.
    """

    allowed: bool
    count: int
    ttl_seconds: int


@runtime_checkable
class RelayRateLimitCounterProtocol(Protocol):
    """Atomic fixed-window counter backend.

    ``take`` must behave atomically for a given ``key``: increment,
    set/refresh expiry on first increment, compare against ``limit``,
    return the decision plus the current window TTL.
    """

    async def take(
        self, key: str, limit: int, window_seconds: int
    ) -> RelayRateLimitDecision: ...


__all__ = ["RelayRateLimitCounterProtocol", "RelayRateLimitDecision"]
