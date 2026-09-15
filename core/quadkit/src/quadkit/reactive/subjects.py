"""Hot multicast primitives: Subject and share()."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any, Generic, TypeVar, cast

from quadkit.concurrency.channels import BoundedChannel
from quadkit.concurrency.exceptions import ChannelClosedError, ChannelFullError
from quadkit.reactive.core import EventStream, Op
from quadkit.reactive.exceptions import BackpressureError

T_subject = TypeVar("T_subject")

# Strong references for share()'s background tasks — asyncio does not keep
# a task alive on its own; see RUF006 and the note under share() below.
_background_tasks: set[asyncio.Task[Any]] = set()

# Sentinel placed in each subscriber channel on complete(); BoundedChannel
# receivers are not woken by close(), so the sentinel is what unblocks them.
_END = object()

# Valid ``on_overflow`` policies; see the Subject class docstring.
_OVERFLOW_MODES = ("block", "drop_latest", "drop_oldest")


class _Failure:
    """Terminal message carrying the exception that ended the stream."""

    __slots__ = ("error",)

    def __init__(self, error: BaseException) -> None:
        self.error = error


class Subscription(Generic[T_subject]):
    """A registered subscriber's handle over its private channel.

    Iterate with ``async for`` to consume replayed history followed by
    live items. When done consuming early (before ``complete()``/
    ``error()`` end the stream), call ``aclose()`` — it detaches the
    channel from the subject's fan-out so the publisher stops buffering
    for a consumer that is gone. Abandoned subscriptions are detached by
    the garbage collector as a safety net.
    """

    def __init__(
        self,
        channel: BoundedChannel[T_subject],
        on_done: Callable[[], None],
    ) -> None:
        self._channel = channel
        self._on_done = on_done
        self._detached = False

    def _detach(self) -> None:
        if not self._detached:
            self._detached = True
            self._on_done()

    def __aiter__(self) -> Subscription[T_subject]:
        return self

    async def __anext__(self) -> T_subject:
        try:
            item = await self._channel.receive()
        except ChannelClosedError:
            self._detach()
            raise StopAsyncIteration from None
        except BaseException:
            # Cancelled or closed mid-receive: stop counting this
            # subscriber immediately, then let the exception propagate.
            self._detach()
            raise
        if isinstance(item, _Failure):
            self._detach()
            raise item.error
        if item is _END:
            self._detach()
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        """Detach from the subject's fan-out; idempotent.

        The channel itself stays open — it belongs to the subject's
        lifecycle — but it no longer receives published items and the
        subject's ``subscriber_count`` drops immediately.
        """
        self._detach()

    def __del__(self) -> None:
        # Safety net for subscribers abandoned without aclose(); keeps
        # subscriber_count honest when consumers vanish via GC.
        with suppress(Exception):
            self._detach()


class Subject(EventStream[T_subject]):
    """A hot, multicast event source.

    Each subscriber iterates a private bounded channel. Publishing fans
    out to every subscriber; ``on_overflow`` decides what happens when a
    subscriber's channel is full:

    - ``"block"`` (default): suspend the producer until there is room.
    - ``"drop_oldest"``: evict the subscriber's oldest queued item and
      deliver the new one — a slow consumer loses backlog, not the live
      feed (the right policy for dashboards and monitors).
    - ``"drop_latest"``: discard the incoming item for that subscriber,
      keeping everything it already has queued.

    ``replay=N`` keeps the newest ``N`` published items in a ring buffer
    and seeds every new subscriber with them, so late joiners see recent
    history before the live feed — the pattern reconnecting SSE clients
    need. Registration is synchronous, so an item published while a
    subscriber is being set up is delivered exactly once: via replay or
    via the channel, never both and never neither.

    Example:
        ```python
        subject = Subject[int](replay=10, on_overflow="drop_oldest")

        async for item in subject:
            print(item)          # subscriber (replays up to 10 items)

        await subject.publish(1)  # producer
        ```
    """

    def __init__(
        self,
        channel_capacity: int = 256,
        on_overflow: str = "block",
        replay: int = 0,
    ) -> None:
        """Initialize a subject.

        Args:
            channel_capacity: Per-subscriber buffer size. ``0`` is unbounded.
            on_overflow: ``"block"``, ``"drop_oldest"`` or ``"drop_latest"``;
                see the class docstring for the policies.
            replay: Number of recent items buffered for late subscribers.
                ``0`` disables replay.

        Raises:
            ValueError: If ``on_overflow`` is not a known mode.
        """
        if on_overflow not in _OVERFLOW_MODES:
            msg = (
                f"unknown on_overflow mode {on_overflow!r}; "
                f"expected one of {_OVERFLOW_MODES}"
            )
            raise ValueError(msg)
        self._capacity = channel_capacity
        self._on_overflow = on_overflow
        self._replay: deque[T_subject] | None = (
            deque(maxlen=replay) if replay > 0 else None
        )
        self._subscribers: list[BoundedChannel[T_subject]] = []
        self._completed = False
        self._failed: BaseException | None = None

    def _new_subscriber(self) -> BoundedChannel[T_subject]:
        channel = BoundedChannel[T_subject](capacity=self._capacity)
        self._subscribers.append(channel)
        return channel

    def _forget(self, channel: BoundedChannel[T_subject]) -> None:
        with suppress(ValueError):
            self._subscribers.remove(channel)

    @property
    def subscriber_count(self) -> int:
        """Number of subscribers currently attached to the fan-out."""
        return len(self._subscribers)

    def replay_snapshot(self) -> list[T_subject]:
        """Copy of the replay buffer, oldest item first."""
        return list(self._replay) if self._replay is not None else []

    def _replay_seed(self) -> list[T_subject]:
        """Replay items to hand a new subscriber, newest-last.

        Bounded channels are seeded with at most ``channel_capacity``
        items (the newest ones), so seeding can never overflow them.
        """
        if self._replay is None:
            return []
        items = list(self._replay)
        if 0 < self._capacity < len(items):
            items = items[-self._capacity :]
        return items

    async def publish(self, item: T_subject) -> None:
        """Fan out an item to all subscribers.

        The item is appended to the replay buffer (if any) before the
        fan-out, so a subscriber registering mid-publish sees it exactly
        once. With a drop mode the fan-out never suspends, which keeps
        ``publish`` atomic with respect to the event loop.

        Args:
            item: Item to publish.

        Raises:
            BackpressureError: With ``on_overflow="drop_oldest"`` when a
                subscriber channel is somehow still full after eviction.
        """
        if self._completed:
            return
        if self._replay is not None:
            self._replay.append(item)
        for channel in list(self._subscribers):
            if self._on_overflow == "block":
                await channel.send(item)
            elif self._on_overflow == "drop_latest":
                with suppress(ChannelFullError):
                    channel.send_nowait(item)
            else:  # drop_oldest
                try:
                    channel.send_nowait(item)
                except ChannelFullError:
                    with suppress(asyncio.QueueEmpty):
                        channel.receive_nowait()
                    try:
                        channel.send_nowait(item)
                    except ChannelFullError as exc:
                        msg = "subscriber channel full"
                        raise BackpressureError(msg) from exc

    async def _terminate(self, terminal: Any) -> None:
        """Send one terminal message per subscriber, then close channels."""
        self._completed = True
        for channel in list(self._subscribers):
            if channel.is_closed:
                continue
            try:
                channel.send_nowait(terminal)
            except ChannelFullError:
                with suppress(asyncio.QueueEmpty):
                    channel.receive_nowait()
                with suppress(ChannelFullError):
                    channel.send_nowait(terminal)
            await channel.close()

    async def complete(self) -> None:
        """Close all subscriber channels; remaining buffered items drain."""
        await self._terminate(cast("T_subject", _END))

    async def error(self, exc: BaseException) -> None:
        """Terminate all subscribers by raising ``exc`` at their next item.

        Args:
            exc: The exception consumers will observe.

        Note:
            Publishes after ``error()`` are ignored, mirroring ``complete()``.
        """
        self._failed = exc
        await self._terminate(_Failure(exc))

    def subscribe(self) -> Subscription[T_subject]:
        """Register a subscriber and return its handle.

        Registration is synchronous (no awaits), so no publish can slip
        between seeding the replay history and joining the live fan-out.

        Returns:
            A :class:`Subscription` yielding replayed history followed by
            live items. Close it early with ``await subscription.aclose()``.
        """
        channel = self._new_subscriber()
        for buffered in self._replay_seed():
            channel.send_nowait(buffered)
        if self._failed is not None:
            channel.send_nowait(cast("T_subject", _Failure(self._failed)))
        elif self._completed:
            channel.send_nowait(cast("T_subject", _END))
        return Subscription(channel, on_done=lambda: self._forget(channel))

    def __aiter__(self) -> AsyncIterator[T_subject]:
        """Iterate this subject's own subscriber channel (one per iterator)."""
        return self.subscribe()

    def pipe(self, *operators: Op[Any, Any]) -> EventStream[Any]:
        """Apply operators left to right to this subject's stream.

        Args:
            operators: Piped operators; each transforms one stream into another.

        Returns:
            The composed stream.
        """
        result: EventStream[Any] = self
        for operator in operators:
            result = operator(result)
        return result


def share(
    source: EventStream[Any],
    channel_capacity: int = 256,
    on_overflow: str = "block",
    replay: int = 0,
) -> Subject[Any]:
    """Pump a source stream into a hot Subject via a background task.

    Args:
        source: Cold or hot source stream.
        channel_capacity: Per-subscriber buffer size.
        on_overflow: Overflow policy; see :class:`Subject`.
        replay: Number of recent items buffered for late subscribers.

    Returns:
        A Subject fed by the source. Iterating it subscribes to the live feed.

    Note:
        If the pump task fails, subscribers observe the pump's exception at
        their next item (recover upstream with ``ops.catch``); a cancelled
        pump completes the subject cleanly.
    """
    subject = Subject[Any](
        channel_capacity=channel_capacity, on_overflow=on_overflow, replay=replay
    )

    async def _pump() -> None:
        async for item in source:
            await subject.publish(item)

    def _schedule_end(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            exc: BaseException | None = None
        else:
            exc = task.exception()
        end = subject.complete() if exc is None else subject.error(exc)
        end_task = asyncio.get_running_loop().create_task(end)
        _background_tasks.add(end_task)
        end_task.add_done_callback(_background_tasks.discard)

    task = asyncio.create_task(_pump())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(_schedule_end)
    return subject
