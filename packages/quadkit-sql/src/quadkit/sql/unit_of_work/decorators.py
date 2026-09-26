"""Transactional decorator for service methods.

Provides a clean way to wrap async functions in database transactions
with automatic commit/rollback and optional retry on transient failures.

Example:
    @transactional(provider)
    async def transfer_funds(from_id: str, to_id: str, amount: Decimal):
        # All operations here run in a single transaction
        ...

    @transactional(provider, retries=3)
    async def critical_operation():
        # Retries up to 3 times on transient failures
        ...
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    DeadlockError,
    QueryError,
)

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)

# Exceptions that are safe to retry
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DeadlockError,
)


def transactional(
    provider: DatabaseProviderProtocol | None = None,
    *,
    retries: int = 0,
    backoff_factor: float = 0.5,
    max_backoff: float = 10.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[..., Any]:
    """Decorator to wrap an async function in a database transaction.

    Can be used as:
        @transactional(provider)
        async def func(): ...

    Or without provider (requires 'provider' kwarg at call time):
        @transactional(retries=3)
        async def func(provider=None): ...

    Args:
        provider: Database provider. If None, looks for 'provider' in kwargs.
        retries: Number of retry attempts on transient failures.
        backoff_factor: Multiplier for exponential backoff between retries.
        max_backoff: Maximum backoff duration in seconds.
        retryable_exceptions: Tuple of exception types that trigger retry.
    """
    retry_on = retryable_exceptions or RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Resolve provider
            db_provider = provider or kwargs.get("provider")
            if db_provider is None:
                raise ValueError(
                    "transactional: 'provider' must be passed as decorator arg "
                    "or function kwarg",
                )

            last_error: Exception | None = None
            attempts = 1 + retries

            for attempt in range(attempts):
                try:
                    await db_provider.begin_transaction()
                    try:
                        result = await func(*args, **kwargs)
                        await db_provider.commit_transaction()
                        return result
                    except (
                        DatabaseError,
                        QueryError,
                        DatabaseConnectionError,
                        DatabaseTimeoutError,
                        DeadlockError,
                    ):
                        await db_provider.rollback_transaction()
                        raise
                except retry_on as exc:
                    last_error = exc
                    if attempt < retries:
                        wait = min(
                            backoff_factor * (2**attempt),
                            max_backoff,
                        )
                        logger.warning(
                            "Transient error in %s (attempt %d/%d), "
                            "retrying in %.1fs: %s",
                            func.__name__,
                            attempt + 1,
                            attempts,
                            wait,
                            exc,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise

            # Should not reach here, but just in case
            if last_error:
                raise last_error

        return wrapper

    return decorator
