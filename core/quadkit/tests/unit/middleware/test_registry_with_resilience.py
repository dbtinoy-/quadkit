"""Tests for MiddlewareRegistry.with_resilience (MiddlewareConfig wiring)."""

from __future__ import annotations

from quadkit.middleware.builtins.resilience import (
    CircuitBreakerMiddleware,
    RateLimiterMiddleware,
    RetryMiddleware,
    TimeoutMiddleware,
)
from quadkit.middleware.config import MiddlewareConfig
from quadkit.middleware.core.registry import MiddlewareRegistry

# Priority order for with_resilience():
# logging(10), correlation_id(20), retry(30), circuit_breaker(40),
# rate_limiter(50), timeout(60), timing(90)
ORDER = [
    "logging",
    "correlation_id",
    "retry",
    "circuit_breaker",
    "rate_limiter",
    "timeout",
    "timing",
]


class TestWithResilience:
    """with_resilience builds resilience middlewares from MiddlewareConfig."""

    def test_builds_from_config_values(self) -> None:
        cfg = MiddlewareConfig(
            default_retry_count=7,
            default_retry_delay=0.5,
            default_timeout=12.5,
            circuit_failure_threshold=9,
            circuit_recovery_timeout=45.0,
            rate_limit_max_requests=13,
            rate_limit_window=15.0,
        )
        middlewares = list(MiddlewareRegistry.with_resilience(cfg).all())
        assert len(middlewares) == len(ORDER)

        retry = middlewares[2]
        assert isinstance(retry, RetryMiddleware)
        assert retry._config.max_attempts == 8  # 7 retries + 1 attempt
        assert retry._config.base_delay == 0.5

        timeout = middlewares[5]
        assert isinstance(timeout, TimeoutMiddleware)
        assert timeout._timeout == 12.5

        cb = middlewares[3]
        assert isinstance(cb, CircuitBreakerMiddleware)
        assert cb._failure_threshold == 9
        assert cb._recovery_timeout == 45.0

        rl = middlewares[4]
        assert isinstance(rl, RateLimiterMiddleware)
        assert rl._max_requests == 13
        assert rl._window_seconds == 15.0

    def test_keeps_default_middleware(self) -> None:
        middlewares = list(MiddlewareRegistry.with_resilience().all())
        kinds = [type(mw).__name__ for mw in middlewares]
        assert "LoggingMiddleware" in kinds
        assert "CorrelationIdMiddleware" in kinds
        assert "TimingMiddleware" in kinds

    def test_priority_order(self) -> None:
        middlewares = list(MiddlewareRegistry.with_resilience().all())
        expected = [
            "LoggingMiddleware",
            "CorrelationIdMiddleware",
            "RetryMiddleware",
            "CircuitBreakerMiddleware",
            "RateLimiterMiddleware",
            "TimeoutMiddleware",
            "TimingMiddleware",
        ]
        assert [type(mw).__name__ for mw in middlewares] == expected
