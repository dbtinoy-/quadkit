"""Retry utilities — thin re-export from quadkit.sql.resilience.core.

The canonical implementation lives in :mod:`quadkit.sql.resilience.core`.
This module is retained to avoid breaking the four database drivers that
import ``retry_call`` from here.  New code should import directly from
``quadkit.sql.resilience.core``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quadkit.sql.resilience.core import retry_call as retry_call


def retry(config: Any = None) -> Callable[..., Any]:
    """Retry decorator — delegates to resilience.core.retry_call.

    Args:
        config: :class:`~quadkit.contracts.resilience.RetryConfig` or ``None``.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        import functools

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_call(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


__all__ = ["retry", "retry_call"]
