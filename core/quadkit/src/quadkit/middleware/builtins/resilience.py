"""Resilience middleware — retry, timeout, circuit breaker, rate limiting."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.infra.resilience import CircuitState
from quadkit.logging import get_logger
from quadkit.middleware.exceptions import (
    MiddlewareCircuitOpenError,
    MiddlewareRateLimitError,
    MiddlewareTimeoutError,
)

if TYPE_CHECKING:
    from quadkit.middleware.types import NextHandler

logger = get_logger(__name__)


class RetryMiddleware:
    """Middleware that retries the downstream handler on transient failures.

    Delegates to :func:`quadkit.resilience.retry` for backoff logic.

    Args:
        catch: Exception types considered retryable. Must be explicitly provided.
        max_retries: Maximum number of retry attempts (excluding the
            initial call).
        delay: Seconds to wait between retries.
    """

    __slots__ = ("_config",)

    def __init__(
        self,
        catch: type[Exception] | tuple[type[Exception], ...],
        max_retries: int = 3,
        delay: float = 0.1,
    ) -> None:
        from quadkit.contracts.infra.resilience.models import RetryConfig

        self._config = RetryConfig(
            max_attempts=max_retries + 1,
            base_delay=delay,
            retry_on=catch if isinstance(catch, tuple) else (catch,),
        )

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Retry downstream on retryable exceptions."""
        import random

        config = self._config
        last_error: Exception | None = None
        delay = config.base_delay
        for attempt in range(config.max_attempts):
            try:
                return await next_handler(context)
            except config.retry_on as exc:
                last_error = exc
                if attempt < config.max_attempts - 1:
                    actual_delay = delay
                    if config.jitter:
                        jitter_scale = (
                            config.jitter if isinstance(config.jitter, float) else 0.1
                        )
                        actual_delay = delay * (
                            1.0 + random.uniform(-jitter_scale, jitter_scale)  # noqa: S311 — retry jitter (non-crypto)
                        )
                        actual_delay = max(0.0, actual_delay)
                    await asyncio.sleep(actual_delay)
                    delay *= config.backoff_factor
        if last_error is not None:
            raise last_error from last_error
        raise RuntimeError("Retry exhausted with no error recorded")  # unreachable


class TimeoutMiddleware:
    """Wrap downstream execution in asyncio.wait_for with configurable timeout."""

    __slots__ = ("_name", "_timeout")

    def __init__(self, timeout: float = 30.0, *, name: str = "timeout") -> None:
        self._timeout = timeout
        self._name = name

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        try:
            return await asyncio.wait_for(
                next_handler(context),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            logger.warning(
                "middleware.timeout",
                middleware=self._name,
                timeout=self._timeout,
            )
            raise MiddlewareTimeoutError(
                f"Middleware '{self._name}' timed out after {self._timeout}s",
            ) from exc


class CircuitBreakerMiddleware:
    """Track failures and open circuit after threshold breaches.

    States: closed → open → half_open → closed (on success) or open (on failure).
    """

    __slots__ = (
        "_failure_count",
        "_failure_threshold",
        "_last_failure_time",
        "_lock",
        "_name",
        "_recovery_timeout",
        "_state",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        *,
        name: str = "circuit_breaker",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._name = name
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state: CircuitState = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise MiddlewareCircuitOpenError(
                        f"Circuit breaker '{self._name}' is open — "
                        f"{self._failure_count} consecutive failures",
                    )

        try:
            result = await next_handler(context)
        except Exception as _cb_err:  # circuit breaker must intercept any failure to update its state before re-raising
            async with self._lock:
                self._record_failure()
            raise

        async with self._lock:
            self._record_success()
        return result

    def _should_attempt_recovery(self) -> bool:
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._recovery_timeout

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "middleware.circuit_breaker.opened",
                middleware=self._name,
                failures=self._failure_count,
            )
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.info(
                "middleware.circuit_breaker.reopened",
                middleware=self._name,
            )

    def _record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                "middleware.circuit_breaker.closed",
                middleware=self._name,
            )
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED


class RateLimiterMiddleware:
    """Token bucket rate limiting per middleware instance."""

    __slots__ = (
        "_last_refill",
        "_lock",
        "_max_requests",
        "_name",
        "_tokens",
        "_window_seconds",
    )

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: float = 60.0,
        *,
        name: str = "rate_limiter",
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._name = name
        self._tokens = float(max_requests)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        async with self._lock:
            self._refill()
            if self._tokens < 1.0:
                raise MiddlewareRateLimitError(
                    f"Rate limit exceeded for '{self._name}': "
                    f"{self._max_requests} requests per {self._window_seconds}s",
                )
            self._tokens -= 1.0
        return await next_handler(context)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed >= self._window_seconds:
            self._tokens = float(self._max_requests)
            self._last_refill = now


__all__ = [
    "CircuitBreakerMiddleware",
    "RateLimiterMiddleware",
    "RetryMiddleware",
    "TimeoutMiddleware",
]
