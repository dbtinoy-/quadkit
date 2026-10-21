"""Bounded async channels for producer-consumer communication.

Provides :class:`BoundedChannel` — an ``asyncio.Queue`` wrapper with
backpressure, context-variable propagation (OTel trace spans), and
async-iteration support.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import contextvars
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from quadkit.concurrency.exceptions import ChannelClosedError, ChannelFullError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

T = TypeVar("T")


@dataclass
class _ContextualItem(Generic[T]):
    """Wraps an item with the sender's ``contextvars.Context`` for OTel propagation."""

    item: T
    ctx: contextvars.Context


class BoundedChannel(Generic[T]):
    """Bounded async channel with backpressure and context propagation.

    Wraps ``asyncio.Queue`` and captures ``contextvars.Context`` on send so
    that receivers automatically inherit the sender's OTel trace span.
    """

    #: Default capacity applied when ``capacity`` is omitted.  ``0`` means
    #: unbounded (the historical default); set via :meth:`configure`, which
    #: is invoked at boot from ``ConcurrencyConfig.default_channel_capacity``.
    _default_capacity: int = 0

    @classmethod
    def configure(cls, default_capacity: int) -> None:
        """Set the default capacity for channels created without one.

        Args:
            default_capacity: Capacity used when ``capacity`` is omitted
                (``0`` = unbounded).  Existing channels are unaffected.
        """
        cls._default_capacity = int(default_capacity)

    def __init__(self, capacity: int | None = None) -> None:
        """Initialize a bounded channel.

        Args:
            capacity: Maximum queue size.  ``0`` means unbounded; ``None``
                (the default) uses the class default set by
                :meth:`configure` (initially ``0`` = unbounded).
        """
        self.capacity = self._default_capacity if capacity is None else capacity
        self._queue: asyncio.Queue[_ContextualItem[T]] = asyncio.Queue(
            maxsize=self.capacity
        )
        self._closed = False
        self._lock = asyncio.Lock()
        #: Set whenever something a waiting receiver cares about happened:
        #: an item arrived or the channel closed. Receivers clear it before
        #: they wait. They never dequeue from a helper task, so an item is
        #: either in the queue or in the consumer's hands — there is no tick
        #: in between where ``is_empty`` lies.
        self._wakeup = asyncio.Event()

    async def send(self, item: T) -> None:
        """Send an item, blocking if the channel is full.

        Args:
            item: The item to send.

        Raises:
            ChannelClosedError: If the channel has been closed.
        """
        # Check closed under lock, but release BEFORE the blocking put()
        # to avoid deadlocking close() when the queue is full.
        async with self._lock:
            if self._closed:
                msg = "Cannot send to closed channel"
                raise ChannelClosedError(msg)

        wrapped = _ContextualItem(item=item, ctx=contextvars.copy_context())
        try:
            await self._queue.put(wrapped)
        except asyncio.CancelledError:
            # If cancelled mid-put, attempt to preserve the item so it
            # is not silently lost.  put_nowait can fail if the queue is
            # full, but that means the item was never actually enqueued.
            with suppress(asyncio.QueueFull):
                self._queue.put_nowait(wrapped)
                self._wakeup.set()
            raise
        except asyncio.QueueFull:
            msg = "Channel is full"
            raise ChannelFullError(
                msg,
                capacity=self.capacity,
            ) from None
        self._wakeup.set()

    def send_nowait(self, item: T) -> None:
        """Send an item without blocking.

        Args:
            item: The item to send.

        Raises:
            ChannelClosedError: If the channel has been closed.
            ChannelFullError: If the channel is at capacity.

        Note:
            This method is **not** safe to call concurrently with :meth:`close`
            from another coroutine.  The ``_closed`` flag is read without
            acquiring ``_lock`` because ``send_nowait`` contains no ``await``
            points and asyncio is single-threaded: a concurrent ``close()``
            call can only interleave at an ``await``, which this method never
            reaches.  The only unsafe scenario is a *thread* calling
            ``close()`` while this runs — avoid that pattern.
        """
        if self._closed:
            msg = "Cannot send to closed channel"
            raise ChannelClosedError(msg)

        wrapped = _ContextualItem(item=item, ctx=contextvars.copy_context())
        try:
            self._queue.put_nowait(wrapped)
        except asyncio.QueueFull:
            msg = "Channel is full"
            raise ChannelFullError(msg, capacity=self.capacity) from None
        self._wakeup.set()

    async def receive(self) -> T:
        """Receive an item, blocking if the channel is empty.

        Returns:
            The received item.

        Raises:
            ChannelClosedError: If the channel is closed and empty.
        """
        wrapped = await self._next_item()
        # Restore sender's context variables so OTel trace spans and other
        # context state are propagated to the consumer.
        for var, value in wrapped.ctx.items():
            var.set(value)
        return wrapped.item

    async def _next_item(self) -> _ContextualItem[T]:
        """Dequeue the next wrapped item, or raise once closed and drained.

        The hot path — an item is already queued — is a plain
        ``get_nowait``. Only an empty channel waits, and it waits on one
        wake-up that both :meth:`send` and :meth:`close` raise. Without the
        close half, ``close()`` could not end an ``async for`` over an empty
        channel, and every consumer loop would outlive the thing it consumed.

        The dequeue itself is always synchronous in the consumer's own task.
        Pulling the item inside a helper task would open a window where the
        queue is already empty but the consumer has not resumed yet — a
        caller polling ``is_empty`` (the event bus's ``flush``) would
        conclude the work was done one tick before it started.
        """
        while True:
            try:
                return self._queue.get_nowait()
            except asyncio.QueueEmpty:
                if self._closed:
                    msg = "Channel is closed"
                    raise ChannelClosedError(msg) from None
            # Nothing queued and not closed: both facts were read without an
            # intervening await, so clearing here cannot swallow a wake-up.
            self._wakeup.clear()
            await self._wakeup.wait()

    def receive_nowait(self) -> T:
        """Receive an item without blocking.

        Returns:
            The received item.

        Raises:
            ChannelClosedError: If the channel is closed and empty.
            QueueEmpty: If no item is available.
        """
        try:
            wrapped: _ContextualItem[T] = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            if self._closed:
                msg = "Channel is closed"
                raise ChannelClosedError(msg) from None
            raise
        for var, value in wrapped.ctx.items():
            var.set(value)
        return wrapped.item

    async def close(self) -> None:
        """Close the channel. Remaining items can still be received.

        Receivers blocked on an empty channel are woken and get
        :class:`ChannelClosedError` (``StopAsyncIteration`` under
        ``async for``), so a consumer loop ends when its producer does.
        """
        async with self._lock:
            self._closed = True
            self._wakeup.set()

    @property
    def is_closed(self) -> bool:
        """Whether the channel has been closed."""
        return self._closed

    @property
    def size(self) -> int:
        """Approximate number of items in the channel."""
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """Whether the channel is empty."""
        return self._queue.empty()

    @property
    def is_full(self) -> bool:
        """Whether the channel is at capacity (always ``False`` when unbounded)."""
        if self.capacity == 0:
            return False
        return self._queue.qsize() >= self.capacity

    @asynccontextmanager
    async def sender(self) -> AsyncGenerator[BoundedChannel[T], None]:
        """Context manager that yields ``self`` and closes the channel on exit."""
        try:
            yield self
        finally:
            await self.close()

    @asynccontextmanager
    async def receiver(self) -> AsyncGenerator[BoundedChannel[T], None]:
        """Context manager that yields ``self`` for async iteration."""
        yield self

    def __aiter__(self) -> AsyncIterator[T]:
        """Return self as an async iterator."""
        return self

    async def __anext__(self) -> T:
        """Return the next item, raising ``StopAsyncIteration`` when closed and empty."""
        try:
            return await self.receive()
        except ChannelClosedError:
            raise StopAsyncIteration from None
        except asyncio.QueueEmpty:
            if self._closed:
                raise StopAsyncIteration from None
            raise
