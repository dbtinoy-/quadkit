"""Idempotency decorator for CQRS command handlers.

Provides :func:`idempotent` and its cache registry.  The decorator prevents
duplicate processing of commands that share an idempotency key.

Example:
    ```python
    from quadkit.events.decorators.idempotent import idempotent

    @idempotent(key_func=lambda cmd: cmd.request_id)
    @command_handler(ProcessPaymentCommand)
    async def handle_payment(command: ProcessPaymentCommand) -> str:
        # Idempotent command handling
        return await payment_service.process(command)
    ```
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, cast

from quadkit import hashing
from quadkit.events.decorators.idempotency_cache import IdempotencyCache

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")

# Registry of every cache used by @idempotent applications — one bounded
# instance per decorated function unless a cache is injected.  Grows with
# the number of decorated functions, never with idempotency keys (each
# instance is bounded by MAX_IDEMPOTENCY_CACHE_SIZE).  Mirrors the
# _handler_registry convention in decorators/handlers.py.
_caches: list[IdempotencyCache] = []

# Sentinel distinguishing a cache miss from a legitimately cached None.
_MISS: object = object()


def idempotent(
    *,
    key_func: Callable[[Any], str] | None = None,
    ttl: int = 3600,
    cache: IdempotencyCache | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Decorator to make command handlers idempotent.

    Uses a cache to prevent duplicate processing of commands with the same key.

    Args:
        key_func: Function to extract idempotency key from command.
            If None, uses the command's idempotency_key attribute.
        ttl: Time-to-live for cached results in seconds.  Entries are
            evicted once this elapses; expired entries are treated as
            cache misses and the handler re-executes.
        cache: Optional injected IdempotencyCache instance.  When None,
            each decorated function gets its own bounded cache.

    Returns:
        Decorator function.

    Example:
        ```python
        @idempotent(key_func=lambda cmd: cmd.request_id)
        @command_handler(ProcessPaymentCommand)
        async def handle_payment(command: ProcessPaymentCommand) -> str:
            # Only executed once per request_id
            return await payment_service.process(command)
        ```
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        effective_cache = cache if cache is not None else IdempotencyCache()
        _caches.append(effective_cache)

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            # Find the command
            command = None
            for arg in args:
                if hasattr(type(arg), "model_fields") or hasattr(
                    type(arg), "__dataclass_fields__"
                ):
                    command = arg
                    break

            if command is None:
                for kwarg in kwargs.values():
                    if hasattr(type(kwarg), "model_fields") or hasattr(
                        type(kwarg), "__dataclass_fields__"
                    ):
                        command = kwarg
                        break

            if command is None:
                return await cast("Any", func)(*args, **kwargs)

            # Get idempotency key
            key: Any
            if key_func:
                key = key_func(command)
            else:
                key = getattr(command, "idempotency_key", None)
                if key is None:
                    # Generate key from command content
                    if hasattr(command, "model_dump_json"):
                        content = command.model_dump_json()
                    else:
                        content = str(command)
                    key = hashing.hash_hex(content)

            cache_key = f"idempotent:{type(command).__name__}:{key}"

            # Check cache; _MISS (not None) flags a miss so handlers that
            # legitimately return None are still deduplicated.
            cached = effective_cache.get(cache_key, _MISS)
            if cached is not _MISS:
                return cached

            # Execute and cache
            result = await cast("Any", func)(*args, **kwargs)
            effective_cache.set(cache_key, result, ttl=float(ttl))

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            command = None
            for arg in args:
                if hasattr(type(arg), "model_fields") or hasattr(
                    type(arg), "__dataclass_fields__"
                ):
                    command = arg
                    break

            if command is None:
                for kwarg in kwargs.values():
                    if hasattr(type(kwarg), "model_fields") or hasattr(
                        type(kwarg), "__dataclass_fields__"
                    ):
                        command = kwarg
                        break

            if command is None:
                return func(*args, **kwargs)

            key: Any
            if key_func:
                key = key_func(command)
            else:
                key = getattr(command, "idempotency_key", None)
                if key is None:
                    if hasattr(command, "model_dump_json"):
                        content = command.model_dump_json()
                    else:
                        content = str(command)
                    key = hashing.hash_hex(content)
            cache_key = f"idempotent:{type(command).__name__}:{key}"

            # Check cache; _MISS (not None) flags a miss so handlers that
            # legitimately return None are still deduplicated.
            cached = effective_cache.get(cache_key, _MISS)
            if cached is not _MISS:
                return cached

            result = func(*args, **kwargs)
            effective_cache.set(cache_key, result, ttl=float(ttl))

            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return cast("Callable[P, Any]", async_wrapper)
        return cast("Callable[P, Any]", sync_wrapper)

    return decorator


def clear_idempotency_cache() -> None:
    """Clear every idempotency cache created by the :func:`idempotent` decorator.

    Useful for testing or when caches need to be reset.
    """
    for cache in _caches:
        cache.clear()


__all__ = ["clear_idempotency_cache", "idempotent"]
