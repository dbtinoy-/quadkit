"""Decorators for monitoring — combined timing and structured operation logging."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
import time
from typing import Any, TypeVar

from quadkit.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "monitor",
]


def monitor(
    name: str | None = None,
    *,
    log_args: bool = False,
) -> Callable[[F], F]:
    """Wrap a function with combined structured logging and wall-clock timing.

    Convenience alternative to stacking ``@traced`` and ``@metered``. Emits
    ``operation_start``, ``operation_end``, and ``operation_error`` log events
    with the elapsed duration in milliseconds. Works for both async and sync
    callables.

    Args:
        name: Metric/span name. Defaults to ``"{module}.{qualname}"``.
        log_args: When ``True``, the number of positional arguments is
            included in the log context. Defaults to ``False`` to avoid
            inadvertently logging sensitive data.

    Returns:
        Decorator that wraps the target function with monitoring machinery.

    Example::

        @monitor("user_service.create")
        async def create_user(email: str) -> User:
            return await repo.save(User(email=email))

        @monitor()
        def compute_score(data: list[float]) -> float:
            return sum(data) / len(data)
    """

    def decorator(fn: F) -> F:
        operation = name or f"{fn.__module__}.{fn.__qualname__}"

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                log_ctx: dict[str, Any] = {"operation": operation}
                if log_args:
                    log_ctx["args_count"] = len(args)
                logger.debug("operation_start", **log_ctx)
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    logger.debug("operation_end", duration_ms=elapsed_ms, **log_ctx)
                    return result
                except Exception as exc:  # noqa: BLE001
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    logger.error(
                        "operation_error",
                        duration_ms=elapsed_ms,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        **log_ctx,
                    )
                    raise

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            log_ctx: dict[str, Any] = {"operation": operation}
            if log_args:
                log_ctx["args_count"] = len(args)
            logger.debug("operation_start", **log_ctx)
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug("operation_end", duration_ms=elapsed_ms, **log_ctx)
                return result
            except Exception as exc:  # noqa: BLE001
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "operation_error",
                    duration_ms=elapsed_ms,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    **log_ctx,
                )
                raise

        return sync_wrapper  # type: ignore[return-value]

    return decorator
