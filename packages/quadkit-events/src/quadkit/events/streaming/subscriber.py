"""Event subscriber for consuming event streams.

The subscriber connects to event stores and processes events.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.events.messages.event import Event
    from quadkit.events.stores.base import EventStoreProtocol

from quadkit.logging import get_logger

logger = get_logger(__name__)


class SubscriptionState(StrEnum):
    """State of a subscription."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class Subscription:
    """Represents an event subscription."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    group_id: str | None = None  # MF-03: Group ID for competing consumers
    partition: int | None = None
    total_partitions: int | None = None
    event_types: set[type[Event]] = field(default_factory=set)
    handler: Callable | None = None
    state: SubscriptionState = SubscriptionState.ACTIVE
    position: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_event_at: datetime | None = None
    events_processed: int = 0
    errors: int = 0


class EventSubscriber:
    """Subscribes to and consumes event streams.

    Supports:
    - Multiple subscriptions
    - Position tracking (checkpoints / CheckpointStore)
    - Automatic retry
    - Catch-up subscriptions
    - Competing Consumer Groups (MF-03)
    """

    def __init__(
        self,
        event_store: EventStoreProtocol | None = None,
        checkpoint_store: Any | None = None,
        checkpoint_interval: int = 100,
        total_partitions: int = 4,  # Default partitions for groups
    ):
        """Initialize the subscriber."""
        self._event_store = event_store
        self._checkpoint_store = checkpoint_store
        self._checkpoint_interval = checkpoint_interval
        self._total_partitions = total_partitions
        self._subscriptions: dict[UUID, Subscription] = {}
        self._running = False
        self._tasks: dict[UUID, asyncio.Task] = {}

    async def subscribe(
        self,
        name: str,
        handler: Callable[[Event], Any],
        event_types: set[type[Event]] | None = None,
        from_position: int = 0,
        group_id: str | None = None,
        partition: int | None = None,
    ) -> Subscription:
        """Create a subscription."""
        # IF group_id is provided, try to load position from checkpoint store
        position = from_position
        if group_id and self._checkpoint_store and partition is not None:
            checkpoint_name = f"sub:{group_id}:{name}:{partition}"
            position = (
                await self._checkpoint_store.get_checkpoint(checkpoint_name)
                or from_position
            )

        subscription = Subscription(
            name=name,
            group_id=group_id,
            partition=partition,
            total_partitions=self._total_partitions if group_id else None,
            event_types=event_types or set(),
            handler=handler,
            position=position,
        )

        self._subscriptions[subscription.id] = subscription
        return subscription

    async def unsubscribe(self, subscription_id: UUID) -> bool:
        """Remove a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            True if subscription was removed
        """
        if subscription_id in self._subscriptions:
            # Stop task if running
            if subscription_id in self._tasks:
                self._tasks[subscription_id].cancel()
                del self._tasks[subscription_id]

            del self._subscriptions[subscription_id]
            return True
        return False

    def get_subscription(self, subscription_id: UUID) -> Subscription | None:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def get_subscriptions(self) -> list[Subscription]:
        """Get all subscriptions."""
        return list(self._subscriptions.values())

    async def start(self) -> None:
        """Start consuming events for all subscriptions."""
        self._running = True

        for sub_id, subscription in self._subscriptions.items():
            if subscription.state == SubscriptionState.ACTIVE:
                self._tasks[sub_id] = asyncio.create_task(self._consume(subscription))

    async def stop(self) -> None:
        """Stop consuming events."""
        self._running = False

        for task in self._tasks.values():
            task.cancel()

        self._tasks.clear()

    async def pause(self, subscription_id: UUID) -> bool:
        """Pause a subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if subscription:
            subscription.state = SubscriptionState.PAUSED
            if subscription_id in self._tasks:
                self._tasks[subscription_id].cancel()
                del self._tasks[subscription_id]
            return True
        return False

    async def resume(self, subscription_id: UUID) -> bool:
        """Resume a subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if subscription and subscription.state == SubscriptionState.PAUSED:
            subscription.state = SubscriptionState.ACTIVE
            if self._running:
                self._tasks[subscription_id] = asyncio.create_task(
                    self._consume(subscription),
                )
            return True
        return False

    async def _consume(self, subscription: Subscription) -> None:
        """Consume events for a subscription."""
        if not self._event_store:
            return

        owner_id = str(uuid4())
        checkpoint_name = subscription.name
        if subscription.group_id:
            if subscription.partition is not None:
                checkpoint_name = f"sub:{subscription.group_id}:{subscription.name}:{subscription.partition}"
            else:
                checkpoint_name = f"sub:{subscription.group_id}:{subscription.name}"

        try:
            while self._running and subscription.state == SubscriptionState.ACTIVE:
                # MF-03: Acquire lock if using group_id
                locked = True
                if subscription.group_id and self._checkpoint_store:
                    locked = await self._checkpoint_store.acquire_lock(
                        checkpoint_name,
                        owner_id,
                        timeout=30.0,
                    )

                if not locked:
                    await asyncio.sleep(5.0)  # Wait for lease to expire or be released
                    continue

                try:
                    async for event in self._event_store.stream_all(  # type: ignore[attr-defined]
                        from_position=subscription.position,
                        partition=subscription.partition,
                        total_partitions=subscription.total_partitions,
                    ):
                        # Subscription state may change while the
                        # generator is suspended on each yield.
                        if (
                            not self._running
                            or subscription.state != SubscriptionState.ACTIVE
                        ):
                            break  # type: ignore[unreachable]

                        # Filter by event type if specified
                        if (
                            subscription.event_types
                            and type(event) not in subscription.event_types
                        ):
                            continue

                        # Process event
                        try:
                            if subscription.handler:
                                result = subscription.handler(event)
                                if asyncio.iscoroutine(result):
                                    await result

                            subscription.events_processed += 1
                            subscription.last_event_at = datetime.now(UTC)

                            # Update position
                            position = getattr(event, "sequence_number", None)
                            if position:
                                subscription.position = position

                                # Periodic checkpointing
                                if (
                                    subscription.events_processed
                                    % self._checkpoint_interval
                                    == 0
                                ):
                                    if self._checkpoint_store:
                                        await self._checkpoint_store.save_checkpoint(
                                            checkpoint_name,
                                            position,
                                        )

                        except Exception as e:  # noqa: BLE001 — per-message isolation; one bad message must not kill the subscription
                            subscription.errors += 1
                            logger.exception(
                                "Error processing subscription %s message",
                                subscription.id,
                                error=str(e),
                            )

                    # Final checkpoint for this batch
                    if self._checkpoint_store and subscription.position > 0:
                        await self._checkpoint_store.save_checkpoint(
                            checkpoint_name,
                            subscription.position,
                        )

                finally:
                    # Release lock if using group_id
                    if subscription.group_id and self._checkpoint_store:
                        await self._checkpoint_store.release_lock(
                            checkpoint_name, owner_id
                        )

                if self._running:
                    await asyncio.sleep(1.0)  # Small gap before re-acquiring

        except Exception as e:  # noqa: BLE001 — subscription consumer background task; log and mark ERROR state
            logger.exception()
            subscription.state = SubscriptionState.ERROR

    async def events(self, subscription_id: UUID, batch_size: int = 100) -> Any:
        """Async generator for subscription events.

        Args:
            subscription_id: Subscription ID
            batch_size: Events per batch

        Yields:
            Events from the subscription
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription or not self._event_store:
            return

        async for event in self._event_store.stream_all(  # type: ignore[attr-defined]
            from_position=subscription.position,
            batch_size=batch_size,
            partition=subscription.partition,
            total_partitions=subscription.total_partitions,
        ):
            # Filter by type if specified
            if subscription.event_types and type(event) not in subscription.event_types:
                continue

            # Update position
            position = getattr(event, "sequence_number", None)
            if position:
                subscription.position = position

            yield event


__all__ = ["EventSubscriber", "Subscription", "SubscriptionState"]
