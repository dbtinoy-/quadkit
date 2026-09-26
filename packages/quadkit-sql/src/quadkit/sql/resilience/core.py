"""Database resilience primitives.

When a :class:`~quadkit.contracts.resilience.ResiliencePipelineFactory` is
injected (provided by ``the optional provider``), builds real circuit-breaker /
retry pipelines with database-specific defaults.  When ``None`` is injected
(or ``the optional provider`` is not installed), a lightweight no-op pass-through
is used instead — so ``quadkit-sql`` has **no** hard runtime dependency on the
resilience extension.

Cross-extension communication follows the contracts + DI pattern from
``AGENTS.md``.  ``quadkit-sql`` never imports from ``the optional provider``
directly; it only consumes the :class:`~quadkit.contracts.resilience.ResiliencePipelineFactory`
protocol resolved through the container.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.contracts.infra.resilience import (
    CircuitBreakerConfig,
    ResiliencePipelineFactoryProtocol,
    ResiliencePipelineProtocol,
    RetryConfig,
    TimeoutConfig,
)
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    ConnectionPoolError,
    ConnectionTimeoutError,
    DatabaseConnectionError,
    DeadlockError,
    SerializationError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

T = TypeVar("T")

# Database-specific retryable exceptions
DB_RETRYABLE_EXCEPTIONS = (
    DatabaseConnectionError,
    ConnectionTimeoutError,
    ConnectionPoolError,
    DeadlockError,
    SerializationError,
)


class _NoOpPipeline:
    """Pass-through pipeline used when the optional provider is not installed."""

    async def execute(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Call the function directly without any resilience wrapping."""
        return await func(*args, **kwargs)


class DatabaseResilienceHandler:
    """Manages resilience pipelines for database operations.

    Accepts an optional :class:`~quadkit.contracts.resilience.ResiliencePipelineFactory`
    injected by the DI container.  When a factory is present it builds real
    circuit-breaker / retry pipelines with database-specific defaults.  When
    ``None`` is passed a lightweight no-op pipeline is used, so ``quadkit-sql``
    has no hard runtime dependency on ``the optional provider``.
    """

    def __init__(
        self,
        pipeline_factory: ResiliencePipelineFactoryProtocol | None = None,
    ) -> None:
        """Initialise the resilience handler.

        Args:
            pipeline_factory: Optional factory provided by ``the optional provider``
                via the DI container.  Pass ``None`` for no-op behaviour.
        """
        self._pipeline_factory = pipeline_factory
        self._pipelines: dict[str, ResiliencePipelineProtocol | _NoOpPipeline] = {}
        # optional configuration dicts populated by provider
        self.retry_config: dict[str, Any] | None = None
        self.circuit_config: dict[str, Any] | None = None
        self.timeout_config: dict[str, Any] | None = None

    def get_pipeline(self, name: str) -> ResiliencePipelineProtocol | _NoOpPipeline:
        """Get or create a resilience pipeline for a named database operation.

        Args:
            name: The name of the pipeline (usually the provider name).

        Returns:
            A :class:`~quadkit.contracts.resilience.ResiliencePipelineProtocol`
            when a factory was injected, otherwise a pass-through no-op pipeline.
        """
        if name not in self._pipelines:
            self._pipelines[name] = self._build_pipeline(name)
        return self._pipelines[name]

    def _build_pipeline(self, name: str) -> ResiliencePipelineProtocol | _NoOpPipeline:
        """Build a resilience pipeline using the injected factory, or fall back to no-op."""
        if self._pipeline_factory is None:
            logger.debug(
                "quadkit_resilience_not_configured",
                note="Using no-op pipeline; inject a ResiliencePipelineFactory for "
                "retry/circuit-breaker support.",
                pipeline=name,
            )
            return _NoOpPipeline()

        cb_kwargs: dict[str, Any] = {
            "failure_threshold": 5,
            "recovery_timeout": 30.0,
            "success_threshold": 2,
            "expected_exception": DB_RETRYABLE_EXCEPTIONS,
        }
        if isinstance(self.circuit_config, dict):
            cb_kwargs.update(self.circuit_config)
        cb_cfg = CircuitBreakerConfig(**cb_kwargs)

        retry_kwargs: dict[str, Any] = {
            "max_attempts": 4,
            "base_delay": 0.5,
            "max_delay": 30.0,
            "jitter": True,
            "retry_on": DB_RETRYABLE_EXCEPTIONS,
        }
        if isinstance(self.retry_config, dict):
            if "max_retries" in self.retry_config:
                retry_kwargs["max_attempts"] = self.retry_config["max_retries"] + 1
            retry_kwargs.update(
                {k: v for k, v in self.retry_config.items() if k != "max_retries"},
            )
        retry_cfg = RetryConfig(**retry_kwargs)

        timeout_kwargs: dict[str, Any] = {"timeout": 30.0}
        if isinstance(self.timeout_config, dict):
            if "timeout_seconds" in self.timeout_config:
                timeout_kwargs["timeout"] = self.timeout_config["timeout_seconds"]
            timeout_kwargs.update(
                {
                    k: v
                    for k, v in self.timeout_config.items()
                    if k != "timeout_seconds"
                },
            )
        timeout_cfg = TimeoutConfig(**timeout_kwargs)

        return self._pipeline_factory(
            retry_cfg,
            cb_cfg,
            timeout_cfg,
        )


# ---------------------------------------------------------------------------
# Standalone retry helper (D3.1)
#
# The four database drivers need a simple retry-on-connection-error function
# that is available *before* the DI container is wired (i.e. during the
# initial pool connection).  This helper uses ``RetryConfig`` from contracts
# so it stays within the boundary rules.
#
# ``quadkit.sql.lib.retry`` re-exports ``retry_call`` from here.
# ---------------------------------------------------------------------------

import asyncio as _asyncio
import random as _random


async def retry_call(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Retry an async callable with exponential back-off and jitter.

    Uses :class:`~quadkit.contracts.resilience.RetryConfig` from contracts
    so the retry policy is always expressed through the standard protocol.

    Args:
        func: Async callable to retry.
        *args: Positional arguments forwarded to *func*.
        config: Retry configuration.  Defaults to ``RetryConfig()`` (3 attempts,
            no delay) when ``None``.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        The return value of *func* on a successful attempt.

    Raises:
        :class:`~the optional provider module`: When all
            attempts are exhausted.
        Any exception raised by *func* that is not in ``config.retry_on``.
    """
    from quadkit.contracts.exceptions.resilience import RetryExhaustedError

    if config is None:
        config = RetryConfig()

    last_exc: Exception | None = None
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            should_retry = (
                isinstance(exc, tuple(config.retry_on)) if config.retry_on else False
            )
            if config.retry_if and not should_retry:
                should_retry = config.retry_if(exc)
            if not should_retry:
                raise
            if attempt < config.max_attempts - 1:
                delay = config.base_delay * (config.backoff_factor**attempt)
                if config.jitter:
                    jitter_range = (
                        config.jitter if isinstance(config.jitter, float) else 0.5
                    )
                    delay = delay * (1.0 + _random.uniform(-jitter_range, jitter_range))  # noqa: S311 — jitter (non-crypto)
                delay = min(delay, config.max_delay)
                await _asyncio.sleep(delay)

    if last_exc is not None:
        raise RetryExhaustedError(
            f"All {config.max_attempts} retry attempts failed",
        ) from last_exc
    raise RetryExhaustedError("Retry failed with no exception captured")
