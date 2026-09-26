"""Retry policy for HTTP client requests.

Local implementation to avoid cross-package imports from the optional provider module.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any

from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


def _calculate_delay(
    attempt: int,
    config: RetryConfig,
    base_delay: float = 0.0,
) -> float:
    """Calculate delay with exponential backoff and optional jitter.

    Args:
        attempt: Zero-based attempt index.
        config: Retry configuration.
        base_delay: Base delay in seconds before applying backoff.

    Returns:
        Computed delay capped at ``config.max_delay``.
    """
    delay = base_delay * (config.backoff_factor**attempt)
    if config.jitter:
        jitter_range = config.jitter if isinstance(config.jitter, float) else 0.5
        delay = delay * (1 + random.uniform(-jitter_range, jitter_range))  # noqa: S311 — retry jitter (non-crypto)
    return min(delay, config.max_delay)


_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _method_is_idempotent(method: str | None) -> bool:
    """Return whether *method* is idempotent under the default retry policy.

    Args:
        method: HTTP method, or None for non-HTTP callers.

    Returns:
        True for ``GET``/``HEAD``/``OPTIONS`` (case-insensitive) and for
        None (non-HTTP callers — gate inactive); False for all other methods.
    """
    if method is None:
        return True
    return method.upper() in _IDEMPOTENT_METHODS


class RetryPolicy:
    """Retry policy for HTTP client requests.

    Executes an async callable with configurable retry logic, exponential
    backoff, and per-exception filtering.  Decision semantics follow the
    canonical :mod:`the optional provider module` retry implementation for the
    shared :class:`~quadkit.contracts.infra.resilience.models.RetryConfig`:

    * ``max_attempts`` is the *total* number of attempts including the
      initial try (``max_attempts=1`` never retries).
    * ``abort_on`` exceptions (and ``abort_if`` results) are never
      retried, regardless of ``retry_on``.
    * A successful result is retried only when ``retry_on_result`` is
      configured and returns True for it.
    * An exception is retried only when it matches ``retry_on`` **and**
      passes ``retry_if`` (when configured).
    * ``on_retry(attempt, error)`` is invoked before each retry; callback
      failures are logged, never propagated.
    * http-specific: with ``idempotent_methods_only`` (default True),
      non-idempotent methods (anything but GET/HEAD/OPTIONS) are never
      retried.

    Args:
        config: Retry configuration controlling max retries, delays, and
            which exceptions trigger a retry.
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        method: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute an async function with retries.

        Args:
            func: Async callable to execute.
            *args: Positional arguments forwarded to *func*.
            method: The HTTP method of the request, used only for the
                idempotency gate (never forwarded to *func*). When ``None``
                (non-HTTP callers) the gate is inactive.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func* on success.

        Raises:
            Exception: The last exception raised when all retries are
                exhausted (the original exception, re-raised as-is).
        """
        config = self.config
        last_exception: Exception | None = None

        for attempt in range(config.max_attempts):
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — retry policy must capture any exception to evaluate retry_on config
                last_exception = exc
                if not self._retryable_error(exc, attempt, method):
                    raise
                self._notify_retry(attempt + 1, exc)
                await asyncio.sleep(
                    _calculate_delay(attempt, config, config.base_delay)
                )
            else:
                if not self._retryable_result(result, attempt):
                    return result
                self._notify_retry(attempt + 1, None)
                await asyncio.sleep(
                    _calculate_delay(attempt, config, config.base_delay)
                )

        # Every attempt raised; re-raise the last one.
        assert last_exception is not None
        raise last_exception

    def _retryable_error(
        self,
        error: Exception,
        attempt: int,
        method: str | None,
    ) -> bool:
        """Canonical error-path decision (abort_on → retry_on → retry_if)."""
        config = self.config
        if attempt + 1 >= config.max_attempts:
            return False
        if config.abort_on and isinstance(error, config.abort_on):
            return False
        if not isinstance(error, config.retry_on):
            return False
        if config.retry_if is not None and not config.retry_if(error):
            return False
        if config.idempotent_methods_only:
            return _method_is_idempotent(method)
        return True

    def _retryable_result(self, result: Any, attempt: int) -> bool:
        """Canonical result-path decision (abort_if → retry_on_result)."""
        config = self.config
        if attempt + 1 >= config.max_attempts:
            return False
        if config.abort_if is not None and config.abort_if(result):
            return False
        if config.retry_on_result is None:
            return False
        return bool(config.retry_on_result(result))

    def _notify_retry(self, attempt: int, error: Exception | None) -> None:
        """Invoke the on_retry callback; callback failures never propagate."""
        if self.config.on_retry is None:
            return
        try:
            self.config.on_retry(attempt, error)
        except Exception:  # noqa: BLE001 — a broken callback must not fail the request
            logger.exception("Error in retry callback")


__all__ = ["RetryPolicy"]
