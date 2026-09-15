"""Parallel execution utilities — thin asyncio.TaskGroup wrapper."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit.contracts.core import ExecutionStrategy

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Iterable

T = TypeVar("T")
R = TypeVar("R")


class Parallel:
    """Structured parallel execution via asyncio.

    Provides a high-level API for running multiple async operations
    with different execution strategies.
    """

    @staticmethod
    async def map(
        items: Iterable[T],
        func: Callable[[T], Awaitable[R]],
    ) -> list[R]:
        """Apply an async function to each item in parallel.

        Args:
            items: Items to process.
            func: Async function to apply to each item.

        Returns:
            Results in the same order as items.
        """
        return list(await asyncio.gather(*[func(item) for item in items]))

    @staticmethod
    async def gather(
        *awaitables: Awaitable[T],
    ) -> list[T]:
        """Run awaitables in parallel and return all results.

        Raises on first exception.

        Args:
            awaitables: Awaitables to run concurrently.

        Returns:
            Results in the same order as awaitables.
        """
        return list(await asyncio.gather(*awaitables))

    @staticmethod
    async def all_settled(
        *awaitables: Awaitable[T],
    ) -> list[T | BaseException]:
        """Run all awaitables and return results or exceptions for each.

        Never raises — exceptions are returned as values.

        Args:
            awaitables: Awaitables to run concurrently.

        Returns:
            Results or exceptions in the same order.
        """
        return list(await asyncio.gather(*awaitables, return_exceptions=True))

    @staticmethod
    async def execute(
        *awaitables: Awaitable[T],
        strategy: ExecutionStrategy = ExecutionStrategy.GATHER,
    ) -> Any:
        """Execute multiple awaitables with a specific strategy.

        Args:
            awaitables: The awaitables to execute.
            strategy: The execution strategy to use.

        Returns:
            List of results. For ALL_SETTLED, exceptions are included as values.
            For RACE, returns the first completed result.
        """
        if strategy == ExecutionStrategy.ALL_SETTLED:
            return await asyncio.gather(*awaitables, return_exceptions=True)
        if strategy == ExecutionStrategy.RACE:
            task_list: list[asyncio.Task[T]] = [
                asyncio.create_task(cast("Coroutine[Any, Any, T]", a))
                for a in awaitables
            ]
            done, pending = await asyncio.wait(
                task_list, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            return next(iter(done)).result()
        if strategy == ExecutionStrategy.AS_COMPLETED:
            results = []
            for coro in asyncio.as_completed(list(awaitables)):
                results.append(await coro)
            return results
        # Default: GATHER
        return list(await asyncio.gather(*awaitables))


__all__ = ["Parallel"]
