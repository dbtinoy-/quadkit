"""Convenience bulk combinators built on :class:`BulkOperation`."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from quadkit.workflow.bulk.models import R, T
from quadkit.workflow.bulk.operation import BulkOperation

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable

    from quadkit.workflow.bulk.models import BulkBatchResult
    from quadkit.workflow.config import BulkOperationConfig

__all__ = [
    "bulk_filter",
    "bulk_map",
    "bulk_reduce",
]


async def bulk_map(
    func: Callable[[T], R],
    items: list[T] | AsyncIterable[T],
    config: BulkOperationConfig | None = None,
) -> list[R]:
    """Apply a function to each item and return results."""

    async def processor(batch: list[T]) -> list[R]:
        return [func(item) for item in batch]

    operation = BulkOperation(config, processor)
    results = []
    async for batch_result in operation.execute(items):
        results.extend(batch_result.results)
    return results


async def bulk_filter(
    items: list[T] | AsyncIterable[T],
    predicate: Callable[[T], Awaitable[bool]],
    config: BulkOperationConfig | None = None,
) -> AsyncIterator[BulkBatchResult[T, T]]:
    """Filter items using a predicate function in batches."""

    async def processor(batch: list[T]) -> list[T]:
        tasks = [predicate(item) for item in batch]
        results = await asyncio.gather(*tasks)
        return [item for item, keep in zip(batch, results, strict=False) if keep]

    operation = BulkOperation(config, processor)
    operation._allow_variable_results = True
    async for result in operation.execute(items):
        yield result


async def bulk_reduce(
    items: list[T] | AsyncIterable[T],
    reducer: Callable[[R, T], Awaitable[R]],
    initial: R,
    config: BulkOperationConfig | None = None,
) -> R:
    """Reduce items using a reducer function sequentially."""
    result = initial
    if hasattr(items, "__aiter__"):
        async for item in items:
            result = await reducer(result, item)
    else:
        for item in items:
            result = await reducer(result, item)
    return result
