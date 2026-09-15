"""Transform operators: map, filter, scan, distinct."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from quadkit.reactive.core import EventStream, Stream


def map(transform: Callable[[Any], Any]) -> Any:  # noqa: A001
    """Apply a transform to each item.

    Args:
        transform: Sync callable, or async callable (coroutine function).

    Returns:
        An operator that maps items to transformed items.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            async for item in source:
                result = transform(item)
                if hasattr(result, "__await__"):
                    result = await result
                yield result

        return Stream(_gen())

    return _op


def filter(predicate: Callable[[Any], Any]) -> Any:  # noqa: A001
    """Keep items for which predicate returns truthy.

    Args:
        predicate: Sync or async predicate.

    Returns:
        An operator that drops non-matching items.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            async for item in source:
                result = predicate(item)
                if hasattr(result, "__await__"):
                    result = await result
                if result:
                    yield item

        return Stream(_gen())

    return _op


def scan(accumulator: Callable[[Any, Any], Any], initial: Any) -> Any:
    """Emit running accumulation.

    Args:
        accumulator: Sync or async two-arg accumulator.
        initial: Seed value.

    Returns:
        An operator emitting the running accumulator value per item.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            state = initial
            async for item in source:
                result = accumulator(state, item)
                if hasattr(result, "__await__"):
                    result = await result
                state = result
                yield state

        return Stream(_gen())

    return _op


def distinct(key: Callable[[Any], Any] | None = None) -> Any:
    """Emit only the first occurrence per key.

    Args:
        key: Optional key extractor. Defaults to identity.

    Returns:
        An operator that drops duplicates.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            seen: set[Any] = set()
            async for item in source:
                item_key = item if key is None else key(item)
                if item_key not in seen:
                    seen.add(item_key)
                    yield item

        return Stream(_gen())

    return _op
