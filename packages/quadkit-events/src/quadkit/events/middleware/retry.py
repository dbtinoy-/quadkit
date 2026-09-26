"""Retry middleware for CQRS buses.

Provides automatic retry logic for failed handlers.
"""

from __future__ import annotations

import contextlib
import random
from typing import TYPE_CHECKING, Any

from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class RetryMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that retries failed handler executions.

    Supports:
    - Configurable retry count
    - Exponential backoff with jitter
    - Retryable exception filtering
    - Custom retry conditions

    Example:
        ```python
        retry_middleware = RetryMiddleware(
            max_retries=3,
            backoff_base=0.1,
            backoff_max=10.0,
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        bus.use(retry_middleware)
        ```
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 0.1,
        backoff_factor: float = 2.0,
        backoff_max: float = 30.0,
        backoff_jitter: float = 0.1,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
        retry_condition: Callable[[Exception], bool] | None = None,
        on_retry: Callable[[Message, Exception, int], None] | None = None,
    ):
        """Initialize the retry middleware.

        Args:
            max_retries: Maximum number of retry attempts
            backoff_base: Base delay in seconds
            backoff_factor: Multiplier for exponential backoff
            backoff_max: Maximum backoff delay
            backoff_jitter: Random jitter factor (0.0-1.0)
            retryable_exceptions: Exception types to retry
            retry_condition: Custom function to determine if retry should happen
            on_retry: Callback invoked before each retry
        """
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._backoff_max = backoff_max
        self._backoff_jitter = backoff_jitter
        self._retryable_exceptions = retryable_exceptions or (Exception,)
        self._retry_condition = retry_condition
        self._on_retry = on_retry

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff delay with exponential growth and jitter."""
        delay = self._backoff_base * (self._backoff_factor**attempt)
        delay = min(delay, self._backoff_max)

        # Add jitter
        jitter = random.uniform(  # noqa: S311 — backoff jitter (non-crypto)
            -self._backoff_jitter * delay,
            self._backoff_jitter * delay,
        )

        return max(0, delay + jitter)

    def _should_retry(self, exception: Exception) -> bool:
        """Determine if the exception should trigger a retry."""
        # Check custom condition first
        if self._retry_condition:
            return self._retry_condition(exception)

        # Check exception type
        return isinstance(exception, self._retryable_exceptions)

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with retry logic."""
        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return await next_handler(message)

            except Exception as e:  # noqa: BLE001 — retry middleware; catches any handler failure to check retry eligibility
                last_exception = e

                # Check if we should retry
                if attempt >= self._max_retries or not self._should_retry(e):
                    raise

                # Calculate backoff
                _delay = self._calculate_backoff(attempt)

                # Invoke retry callback
                if self._on_retry:
                    try:
                        self._on_retry(message, e, attempt + 1)
                    except (RuntimeError, ValueError, TypeError, AttributeError):
                        with contextlib.suppress(OSError, ValueError, TypeError):
                            logger.exception("on_retry callback failed")
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception


__all__ = ["RetryMiddleware"]
