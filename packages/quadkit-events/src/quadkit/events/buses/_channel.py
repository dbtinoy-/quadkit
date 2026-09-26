"""Bounded async channel for internal event bus use.

Provides a stdlib-only backpressure channel that satisfies
:class:`~quadkit.contracts.core.concurrency_protocols.ChannelProtocol`
without importing from any other extension package.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class _EventChannel(Generic[T]):
    """Bounded async channel backed by :class:`asyncio.Queue`.

    Implements the interface expected by :class:`~quadkit.events.buses.event.EventBus`
    — ``send``, ``receiver()`` context manager, ``is_empty``, and ``close``.
    Context-variable propagation is intentionally omitted here; OTel span
    continuity across the channel is provided by the higher-level bus code.

    Args:
        capacity: Maximum queue depth.  ``0`` means unbounded.
    """

    def __init__(self, capacity: int = 0) -> None:
        self.capacity = capacity
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=capacity)
        self._closed = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # ChannelProtocol surface
    # ------------------------------------------------------------------

    async def send(self, item: T) -> None:
        """Enqueue *item*, blocking if the channel is at capacity.

        Args:
            item: The item to send.

        Raises:
            RuntimeError: If the channel has been closed.
        """
        async with self._lock:
            if self._closed:
                raise RuntimeError("Cannot send to a closed channel")
        await self._queue.put(item)

    async def receive(self) -> T:
        """Dequeue the next item, blocking if the channel is empty.

        Returns:
            The next item.

        Raises:
            StopAsyncIteration: If the channel is closed and empty.
        """
        return await self._queue.get()

    async def close(self) -> None:
        """Close the channel; in-flight items can still be received."""
        async with self._lock:
            self._closed = True

    @property
    def closed(self) -> bool:
        """``True`` once :meth:`close` has been called."""
        return self._closed

    # ------------------------------------------------------------------
    # Additional helpers used by EventBus
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """``True`` when no items are currently queued."""
        return self._queue.empty()

    @property
    def is_closed(self) -> bool:
        """Alias for :attr:`closed`."""
        return self._closed

    # ------------------------------------------------------------------
    # Async iteration / context manager helpers
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def receiver(self) -> Any:
        """Async context manager yielding ``self`` as an async iterable."""
        yield self

    def __aiter__(self) -> _EventChannel[T]:
        return self

    async def __anext__(self) -> T:
        """Return the next item; raise :exc:`StopAsyncIteration` when closed and empty."""
        while True:
            if self._closed and self._queue.empty():
                raise StopAsyncIteration
            try:
                return await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                continue  # Re-check closed+empty at top of loop


__all__ = ["_EventChannel"]
