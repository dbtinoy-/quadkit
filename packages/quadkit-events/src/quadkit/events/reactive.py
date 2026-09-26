"""Bridges from the event subsystem into quadkit.reactive streams.

Cold streams replay the event store; hot streams catch up from the store
then tail ``StreamDispatcher`` live events. All imports from
``quadkit.reactive`` are the core layer — this module is the allowed
extension-to-core direction.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any, cast

from quadkit.events.messages.event import Event
from quadkit.events.stores.base import AbstractEventStore
from quadkit.events.streaming.dispatcher import StreamDispatcher
from quadkit.reactive import EventStream, Op, Stream
from quadkit.reactive.retry import RetryOptions, retry


def from_store(
    store: AbstractEventStore,
    from_position: int = 0,
    event_types: list[str] | None = None,
) -> EventStream[Event]:
    """Build a cold replay stream over an event store.

    Args:
        store: Any event store exposing ``stream_all`` / ``stream_by_type``.
        from_position: Global position to replay from. Defaults to 0.
        event_types: Optional event type name filter.

    Returns:
        A cold stream of stored events.

    Example:
        ```python
        async for event in from_store(store, from_position=42):
            process(event)
        ```
    """
    if event_types:
        source = store.stream_by_type(event_types, from_position=from_position)
    else:
        source = store.stream_all(from_position=from_position)
    return Stream(source)


def from_bus(
    dispatcher: StreamDispatcher,
    event_store: AbstractEventStore,
    from_position: int = 0,
    event_types: list[str] | None = None,
) -> EventStream[Event]:
    """Build a catchup-plus-live stream over a dispatcher.

    Args:
        dispatcher: StreamDispatcher that also receives store writes.
        event_store: Store used for the catch-up phase.
        from_position: Global position to replay from. Defaults to 0.
        event_types: Optional event type name filter.

    Returns:
        A hot stream emitting historical events first, then live events.

    Note:
        Cancelling the consumer unsubscribes from the dispatcher.
    """
    from quadkit.reactive.subjects import Subject

    subject = Subject[Event]()

    async def handler(event: Event) -> None:
        await subject.publish(event)

    subscription_id: list[str | None] = [None]
    background_tasks: set[asyncio.Task[Any]] = set()

    async def _start() -> None:
        subscription_id[0] = await dispatcher.subscribe_catchup(
            handler,
            event_store,
            from_position=from_position,
            event_types=event_types,
        )

    start_task = asyncio.create_task(_start())
    background_tasks.add(start_task)
    start_task.add_done_callback(background_tasks.discard)

    async def _gen() -> AsyncIterator[Event]:
        try:
            async for event in subject:
                yield event
        finally:
            if not start_task.done():
                start_task.cancel()
                with suppress(asyncio.CancelledError):
                    await start_task
            if subscription_id[0] is not None:
                dispatcher.unsubscribe(subscription_id[0], handler)
            else:
                dispatcher.unsubscribe(None, handler)

    return Stream(_gen())


def retry_with_resilience(policy: Any) -> Op[Event, Event]:
    """Bridge a resilience policy into the core ``retry`` operator.

    Args:
        policy: A resilience retry policy exposing ``should_retry(error)``.

    Returns:
        A core-compatible retry operator.
    """
    return cast(
        "Callable[[EventStream[Event]], EventStream[Event]]",
        retry(
            RetryOptions(
                max_attempts=int(getattr(policy, "max_attempts", 3)),
                should_retry=getattr(policy, "should_retry", None),
            )
        ),
    )
