"""Event publisher for distributing events.

The dispatcher broadcasts events to all registered stream subscribers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

# Event is used at runtime in cast() calls - import unconditionally
from quadkit.events.messages.event import Event
from quadkit.events.protocols import EventFilterProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class DispatcherStats:
    """Statistics for the stream dispatcher."""

    events_published: int = 0
    events_failed: int = 0
    active_subscribers: int = 0
    last_event_at: datetime | None = None


class StreamDispatcher:
    """Dispatches events to stream subscribers.

    Supports:
    - Multiple subscribers per event type
    - Global subscribers (all events)
    - Per-subscription event filtering
    - Async event delivery
    - Delivery guarantees

    Example:
        ```python
        from quadkit.logging import get_logger

        logger = get_logger(__name__)
        dispatcher = StreamDispatcher()

        # Subscribe to specific events
        dispatcher.subscribe(
            OrderCreatedEvent,
            lambda e: logger.info("order_created", order_id=e.order_id)
        )

        # Subscribe to all events
        dispatcher.subscribe_all(lambda e: logger.info("Event: %s", e))

        # Dispatch event
        await dispatcher.publish(OrderCreatedEvent(order_id="ord-123"))
        ```
    """

    def __init__(self, parallel_delivery: bool = True, continue_on_error: bool = True):
        """Initialize the publisher.

        Args:
            parallel_delivery: Deliver to subscribers in parallel
            continue_on_error: Continue delivery if a subscriber fails
        """
        self._parallel_delivery = parallel_delivery
        self._continue_on_error = continue_on_error
        self._subscribers: dict[type[Event], list[Callable]] = {}
        self._global_subscribers: list[Callable] = []
        self._subscriptions: dict[
            str, tuple[type[Event] | str | None, Callable, EventFilterProtocol | None]
        ] = {}
        self._stats = DispatcherStats()

    @property
    def stats(self) -> DispatcherStats:
        """Get dispatcher statistics."""
        return self._stats

    def subscribe(
        self,
        event_type: type[Event] | str,
        handler: Callable[[Event], Any],
        event_filter: EventFilterProtocol | None = None,
    ) -> str:
        """Subscribe to a specific event type or all events.

        Args:
            event_type: Event type to subscribe to, or "*" for all events
            handler: Handler function
            event_filter: Optional predicate that gates delivery; the
                handler is invoked only for published events where
                ``event_filter.matches(event)`` is True. Accepts
                ``EventFilter``, ``CompositeFilter``, ``NegatedFilter``,
                or any other ``EventFilterProtocol`` implementation.
                Defaults to None, delivering every event of the
                subscribed type.

        Returns:
            Subscription ID

        Example:
            ```python
            from quadkit.events.streaming import EventFilter

            dispatcher = StreamDispatcher()
            dispatcher.subscribe(
                OrderCreatedEvent,
                handle_order_created,
                EventFilter(aggregate_id="order-123"),
            )
            ```

        Note:
            Subscriptions whose filter rejects an event are skipped and
            do not count toward the value returned by ``publish()``.
        """
        subscription_id = str(uuid4())

        # Global subscription
        if event_type == "*":
            self._global_subscribers.append(handler)
            self._subscriptions[subscription_id] = (None, handler, event_filter)
            self._stats.active_subscribers += 1
            return subscription_id

        # Type-specific subscription (narrow to type[Event])
        etype = cast("type[Event]", event_type)
        if etype not in self._subscribers:
            self._subscribers[etype] = []

        self._subscribers[etype].append(handler)
        self._subscriptions[subscription_id] = (etype, handler, event_filter)
        self._stats.active_subscribers += 1

        return subscription_id

    def subscribe_all(self, handler: Callable[[Event], Any]) -> str:
        """Subscribe to all events.

        Args:
            handler: Handler function

        Returns:
            Subscription ID
        """
        self._global_subscribers.append(handler)
        self._stats.active_subscribers += 1
        subscription_id = str(uuid4())
        self._subscriptions[subscription_id] = (None, handler, None)
        return subscription_id

    def _drop_subscriptions(
        self, event_type: type[Event] | None, handler: Callable
    ) -> None:
        """Remove subscription records matching an event type and handler."""
        self._subscriptions = {
            sub_id: entry
            for sub_id, entry in self._subscriptions.items()
            if not (entry[0] == event_type and entry[1] == handler)
        }

    def unsubscribe(
        self,
        subscription_id_or_event_type: str | type[Event] | None,
        handler: Callable | None = None,
    ) -> bool:
        """Unsubscribe a handler.

        Supports either:
        - unsubscribe(subscription_id: str)
        - unsubscribe(event_type: type[Event] | None, handler: Callable)

        Returns:
            True if handler was removed
        """
        # Unsubscribe by subscription id
        if isinstance(subscription_id_or_event_type, str) and handler is None:
            subscription_id = subscription_id_or_event_type
            entry = self._subscriptions.pop(subscription_id, None)
            if not entry:
                return False
            event_type, handler, _ = entry
            if event_type is None:
                if handler in self._global_subscribers:
                    self._global_subscribers.remove(handler)
                    self._stats.active_subscribers -= 1
                    return True
            else:
                handlers = self._subscribers.get(cast("type[Event]", event_type), [])
                if handler in handlers:
                    handlers.remove(handler)
                    self._stats.active_subscribers -= 1
                    return True
            return False

        # Unsubscribe by event_type + handler
        event_type = subscription_id_or_event_type
        if event_type is None:
            if handler in self._global_subscribers:
                self._global_subscribers.remove(handler)
                self._drop_subscriptions(None, handler)
                self._stats.active_subscribers -= 1
                return True
        else:
            handlers = self._subscribers.get(cast("type[Event]", event_type), [])
            if handler in handlers:
                handlers.remove(handler)
                self._drop_subscriptions(cast("type[Event]", event_type), handler)
                self._stats.active_subscribers -= 1
                return True

        return False

    async def publish(self, event: Event) -> int:
        """Publish an event to subscribers.

        Args:
            event: Event to publish

        Returns:
            Number of subscribers notified
        """
        event_type = type(event)
        subscriptions = self._get_subscriptions(event_type)

        if not subscriptions:
            return 0

        handlers = [
            handler
            for handler, event_filter in subscriptions
            if event_filter is None or event_filter.matches(event)
        ]
        if not handlers:
            return 0

        self._stats.events_published += 1
        self._stats.last_event_at = datetime.now(UTC)

        if self._parallel_delivery:
            return await self._deliver_parallel(event, handlers)
        return await self._deliver_sequential(event, handlers)

    async def publish_batch(self, events: list[Event]) -> int:
        """Publish multiple events.

        Args:
            events: Events to publish

        Returns:
            Total subscribers notified
        """
        total = 0
        for event in events:
            total += await self.publish(event)
        return total

    async def subscribe_catchup(
        self,
        handler: Callable[[Event], Any],
        event_store: Any,
        from_position: int = 0,
        event_types: list[str] | None = None,
    ) -> str:
        """M-06: Combined catch-up + live tailing subscription.

        First replays historical events from the store (catch-up phase),
        then registers the handler for future live events — there is no
        gap between the two phases because the live subscription is
        registered *before* replay begins.

        Args:
            handler: Async callable receiving each Event.
            event_store: EventStoreProtocol to replay from.
            from_position: Global position to replay from (0 = all).
            event_types: Optional list of event type names to filter.

        Returns:
            Live subscription ID (use to unsubscribe later).
        """
        # Register live subscription first so we don't miss events
        live_sub_id = self.subscribe_all(handler)

        # Replay historical events (catch-up)
        try:
            if event_types:
                replay_iter = event_store.stream_by_type(
                    event_types, from_position=from_position
                )
            else:
                replay_iter = event_store.stream_all(from_position=from_position)

            async for event in replay_iter:
                await self._call_handler(handler, event)
        except Exception as e:  # noqa: BLE001 — catch-up replay error; log and return live subscription without crashing
            logger.exception("Catch-up replay error", error=str(e))

        return live_sub_id

    def _get_subscriptions(
        self, event_type: type[Event]
    ) -> list[tuple[Callable, EventFilterProtocol | None]]:
        """Get matching (handler, filter) pairs for an event type.

        Includes global subscriptions and type-specific subscriptions
        where the published event type is a subclass of the registered
        type.
        """
        subscriptions: list[tuple[Callable, EventFilterProtocol | None]] = []
        for registered_type, handler, event_filter in self._subscriptions.values():
            if registered_type is None or issubclass(
                event_type, cast("type[Event]", registered_type)
            ):
                subscriptions.append((handler, event_filter))
        return subscriptions

    async def _deliver_parallel(self, event: Event, handlers: list[Callable]) -> int:
        """Deliver to handlers in parallel."""
        tasks = [self._call_handler(handler, event) for handler in handlers]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        failure_count = len(results) - success_count

        self._stats.events_failed += failure_count

        return success_count

    async def _deliver_sequential(self, event: Event, handlers: list[Callable]) -> int:
        """Deliver to handlers sequentially."""
        success_count = 0
        event_type = type(event)

        for handler in handlers:
            try:
                await self._call_handler(handler, event)
                success_count += 1
            except Exception:  # noqa: BLE001 — per-handler isolation: one failing handler must not skip the rest
                import contextlib

                with contextlib.suppress(OSError, ValueError, TypeError):
                    logger.exception(
                        "Publisher handler %s failed for event %s",
                        getattr(handler, "__name__", str(handler)),
                        event_type.__name__,
                    )
                self._stats.events_failed += 1
                if not self._continue_on_error:
                    raise

        return success_count

    async def _call_handler(self, handler: Callable, event: Event) -> None:
        """Call a handler with an event."""
        result = handler(event)
        if asyncio.iscoroutine(result):
            await result


__all__ = ["DispatcherStats", "StreamDispatcher"]
