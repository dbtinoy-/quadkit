"""Shared configuration models for resilience patterns.

These live in contracts so ANY package (quadkit-events, quadkit-web, etc.)
can reference retry/circuit breaker configs without depending on
the the optional provider implementation package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry policy."""

    # Total attempts including the initial try.  max_attempts=3 means one
    # initial call plus up to 2 retries — NOT 3 retries on top of the
    # first try.  Minimum useful value is 1 (no retries).
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool | float = True
    retry_on: tuple[type[Exception], ...] = field(default=(Exception,))
    retry_if: Callable[[Exception], bool] | None = None
    on_retry: Callable[[int, Exception | None], None] | None = None
    retry_on_result: Callable[[Any], bool] | None = None
    abort_on: tuple[type[Exception], ...] = field(default=())
    abort_if: Callable[[Any], bool] | None = None
    retry_sync: bool = False
    # Retry only requests whose HTTP method is idempotent (GET/HEAD/OPTIONS).
    # Defaults to True (safe by default).
    idempotent_methods_only: bool = True


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening the circuit.
        recovery_timeout: Seconds in open state before attempting half-open.
        expected_exception: Exception types that count as failures.
        success_threshold: Consecutive successes required to close from half-open.
        timeout: Per-call timeout in seconds.
        name: Human-readable identifier for this breaker instance.
        sliding_window_seconds: Window for computing the failure rate.
        failure_rate_threshold: Fraction of calls that must fail to trip.
        backend: State store backend for distributed circuit breaker coordination.
            ``"memory"`` (default) — in-process state, no coordination.
            ``"redis"`` — uses a :class:`~quadkit.contracts.cache.CacheBackendProtocol`
            resolved from the DI container.
            ``"consul"`` — uses Consul KV for cross-datacenter coordination.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: tuple[type[Exception], ...] = field(default=(Exception,))
    success_threshold: int = 3
    timeout: float = 30.0
    name: str = ""
    sliding_window_seconds: float = 60.0
    failure_rate_threshold: float = 0.5
    backend: Literal["memory", "redis", "consul"] = "memory"


@dataclass(frozen=True)
class TimeoutConfig:
    """Configuration for timeout handling."""

    timeout: float = 30.0
    timeout_message: str = "Operation timed out"


__all__ = [
    "CircuitBreakerConfig",
    "RetryConfig",
    "TimeoutConfig",
]
