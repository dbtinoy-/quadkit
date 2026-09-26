"""Resilience pattern protocol class definitions."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, Self, runtime_checkable

from quadkit.contracts.infra.resilience.models import (
    CircuitBreakerConfig,
    RetryConfig,
    TimeoutConfig,
)


@runtime_checkable
class CircuitBreakerProtocol(Protocol):
    """Protocol for circuit breaker implementations."""

    @property
    def state(self) -> str:
        """Get current circuit state (closed, open, half_open)."""
        ...

    async def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        ...

    def protect(self) -> AbstractAsyncContextManager[None]:
        """Return an async context manager that protects a code block.

        Raises CircuitOpenError when the circuit is open, and records
        success or failure based on the outcome of the protected block.
        """
        ...

    def reset(self) -> None:
        """Reset circuit to closed state."""
        ...

    def force_open(self) -> None:
        """Force circuit to open state."""
        ...


@runtime_checkable
class RetryPolicyProtocol(Protocol):
    """Protocol for retry policy implementations."""

    async def execute(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute function with retry logic."""
        ...


@runtime_checkable
class BulkheadProtocol(Protocol):
    """Protocol for bulkhead implementations."""

    async def __aenter__(self) -> Self:
        """Enter bulkhead context."""
        ...

    async def __aexit__(self, *args: object) -> None:
        """Exit bulkhead context."""
        ...


@runtime_checkable
class ResiliencePipelineProtocol(Protocol):
    """Protocol for resilience pipeline that combines multiple patterns."""

    def add(self, pattern: Any) -> ResiliencePipelineProtocol:
        """Add a resilience pattern to the pipeline."""
        ...

    async def execute(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute function through the resilience pipeline."""
        ...


@runtime_checkable
class ResiliencePipelineFactoryProtocol(Protocol):
    """Factory protocol for creating configured resilience pipelines.

    ``the optional provider`` registers a concrete implementation.  Other
    extension packages (e.g. ``quadkit-sql``) request an optional
    ``ResiliencePipelineFactory | None`` via DI injection so they can build
    pre-configured pipelines without importing from ``the optional provider``
    directly.

    Example::

        class DatabaseResilienceHandler:
            def __init__(
                self,
                pipeline_factory: ResiliencePipelineFactory | None = None,
            ) -> None:
                self._factory = pipeline_factory
    """

    def __call__(
        self,
        retry_config: RetryConfig,
        circuit_config: CircuitBreakerConfig,
        timeout_config: TimeoutConfig,
    ) -> ResiliencePipelineProtocol:
        """Build and return a configured resilience pipeline.

        Args:
            retry_config: Retry policy settings.
            circuit_config: Circuit-breaker settings.
            timeout_config: Timeout settings.

        Returns:
            A configured :class:`ResiliencePipelineProtocol` instance.
        """
        ...


@runtime_checkable
class CircuitBreakerRegistryProtocol(Protocol):
    """Protocol for circuit breaker registries."""

    def get(self, name: str) -> CircuitBreakerProtocol | None:
        """Get circuit breaker by name."""
        ...

    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreakerProtocol:
        """Get or create circuit breaker by name."""
        ...

    def list_breakers(self) -> dict[str, dict[str, Any]]:
        """List all circuit breakers."""
        ...


@runtime_checkable
class ThrottlerProtocol(Protocol):
    """Protocol for throttler implementations."""

    async def acquire(self) -> None:
        """Acquire permission to proceed."""
        ...

    async def try_acquire(self) -> bool:
        """Try to acquire permission. Returns True if successful."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get throttling statistics."""
        ...


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """Protocol for token-bucket and sliding-window rate limiters.

    ``the optional provider`` is the canonical owner of all rate-limiter
    implementations.  Extension packages declare this protocol as a
    constructor parameter type and receive a concrete implementation via
    the DI container.
    """

    async def acquire(self) -> None:
        """Block until one token is available and consume it."""
        ...

    async def try_acquire(self) -> bool:
        """Consume one token without blocking.

        Returns:
            True if the token was acquired; False if the limit is exhausted.
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return current limiter statistics as a plain mapping."""
        ...


@runtime_checkable
class ResilienceFallbackProtocol(Protocol):
    """Executes a sequence of fallback strategies until one succeeds.

    Strategies are tried in registration order. The chain raises the
    last encountered exception only if all strategies are exhausted.
    """

    def add(self, strategy: Any) -> Self:
        """Append a fallback strategy to the chain.

        Args:
            strategy: Callable or coroutine-returning callable to try.

        Returns:
            Self, for fluent chaining.
        """
        ...

    async def execute(self) -> Any:
        """Execute strategies in order, returning the first success.

        Raises:
            The last exception if every strategy fails.
        """
        ...


@runtime_checkable
class TimeoutProtocol(Protocol):
    """Protocol for timeout policy enforcement.

    Implementations enforce maximum execution time budgets on operations.
    """

    async def execute_with_timeout(
        self,
        coro: Any,
        timeout_seconds: float,
    ) -> Any:
        """Execute a coroutine with a timeout budget.

        Args:
            coro: The coroutine to execute.
            timeout_seconds: Maximum allowed seconds before raising.

        Raises:
            TimeoutError: If execution exceeds the budget.
        """
        ...

    @property
    def default_timeout(self) -> float:
        """The default timeout in seconds used when none is specified."""
        ...


__all__ = [
    "BulkheadProtocol",
    "CircuitBreakerProtocol",
    "CircuitBreakerRegistryProtocol",
    "RateLimiterProtocol",
    "ResilienceFallbackProtocol",
    "ResiliencePipelineFactoryProtocol",
    "ResiliencePipelineProtocol",
    "RetryPolicyProtocol",
    "ThrottlerProtocol",
    "TimeoutProtocol",
]
