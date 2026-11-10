"""Event sourcing repository with snapshot-accelerated loading.

Snapshots avoid reapplying earlier events. Replay and version checks still
have costs determined by the remaining suffix and the event-store backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar
from uuid import UUID

from quadkit.events.aggregates.aggregate import AggregateRoot
from quadkit.events.exceptions import AggregateNotFoundError, EventStoreError
from quadkit.events.repository.base import AbstractRepository
from quadkit.events.stores._history import (
    read_consistent_history,
    validated_stream_version,
)
from quadkit.events.stores.snapshot import SnapshotManager, SnapshotPolicy

if TYPE_CHECKING:
    from quadkit.events.buses.event import EventBusImpl
    from quadkit.events.stores.base import AbstractEventStore, AbstractSnapshotStore

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class EventSourcingRepository(AbstractRepository[TAggregate], Generic[TAggregate]):
    """AbstractRepository using event sourcing with snapshot acceleration.

    This repository:
    1. Loads aggregates using snapshots when available
    2. Persists changes as events
    3. Automatically creates snapshots based on policy
    4. Publishes events to the event bus

    Example:
        ```python
        # Create repository with snapshot support
        repository = EventSourcingRepository(
            aggregate_type=Order,
            event_store=event_store,
            snapshot_store=snapshot_store,
            event_bus=event_bus,
            snapshot_policy=EventCountPolicy(100)
        )

        # Load aggregate - uses snapshot if available
        order = await repository.get(order_id)

        # Modify aggregate
        order.add_item(product_id, quantity, price)

        # Save - stores events, maybe creates snapshot, publishes events
        await repository.save(order)
        ```

    Performance depends on the backend, snapshot size and remaining events.
    """

    def __init__(
        self,
        aggregate_type: type[TAggregate],
        event_store: AbstractEventStore,
        snapshot_store: AbstractSnapshotStore | None = None,
        event_bus: EventBusImpl | None = None,
        snapshot_policy: SnapshotPolicy | None = None,
        snapshot_every: int = 100,
    ):
        """Initialize the event sourcing repository.

        Args:
            aggregate_type: The aggregate class to manage
            event_store: Event store for event persistence
            snapshot_store: Snapshot store (optional, avoids replaying earlier events)
            event_bus: Event bus for publishing events (optional)
            snapshot_policy: Custom snapshot policy (default: every N events)
            snapshot_every: Events between snapshots (default: 100)
        """
        self._aggregate_type = aggregate_type
        self._event_store = event_store
        self._snapshot_store = snapshot_store
        self._event_bus = event_bus
        self._snapshot_manager: SnapshotManager | None = None

        # Setup snapshot manager if snapshot store is provided
        if snapshot_store is not None:
            from quadkit.events.stores.snapshot import EventCountPolicy

            policy = snapshot_policy or EventCountPolicy(snapshot_every)
            self._snapshot_manager = SnapshotManager(
                event_store=event_store,
                snapshot_store=snapshot_store,
                policy=policy,
            )

    async def get(self, aggregate_id: UUID | str) -> TAggregate | None:
        """Load an aggregate; reject snapshots or replay that cannot be applied."""
        stream_id = str(aggregate_id)
        snapshot_state = None
        starting_version = 0
        if self._snapshot_manager is not None:
            (
                snapshot_state,
                events,
                starting_version,
            ) = await self._snapshot_manager.load_with_snapshot(
                aggregate_id=stream_id,
                aggregate_type=self._aggregate_type.__name__,
            )
        else:
            events = await read_consistent_history(self._event_store, stream_id, 0)

        if snapshot_state is None and not events:
            return None

        try:
            identity: UUID | str = UUID(stream_id)
        except ValueError:
            # Some custom stores use non-UUID stream IDs; retain those IDs.
            identity = stream_id

        aggregate = self._aggregate_type()
        try:
            aggregate.id = identity
            aggregate.version = starting_version
            if snapshot_state is not None:
                if "id" in snapshot_state and str(snapshot_state["id"]) != str(
                    identity
                ):
                    raise ValueError("snapshot identity mismatch")
                if "version" in snapshot_state and (
                    type(snapshot_state["version"]) is not int
                    or snapshot_state["version"] != starting_version
                ):
                    raise ValueError("snapshot version mismatch")
                for key, value in snapshot_state.items():
                    if key in {"id", "version"}:
                        continue
                    if (
                        not isinstance(key, str)
                        or key.startswith("_")
                        or not hasattr(aggregate, key)
                    ):
                        raise ValueError("unsupported snapshot field")
                    setattr(aggregate, key, value)

            for event in events:
                event_id = getattr(event, "aggregate_id", None)
                if event_id is not None and str(event_id) != str(identity):
                    raise ValueError("event aggregate identity mismatch")
                # The default implementation silently ignores unknown events;
                # custom _apply implementations own their own dispatch rules.
                if (
                    type(aggregate)._apply is AggregateRoot._apply
                    and aggregate._get_event_handler(type(event)) is None
                ):
                    raise ValueError("event has no aggregate handler")
            if events:
                aggregate.load_from_history(events)
            if str(aggregate.id) != str(identity):
                raise ValueError("aggregate identity changed during replay")
            if aggregate.version != starting_version + len(events):
                raise ValueError("aggregate version changed unexpectedly during replay")
        except Exception as exc:  # noqa: BLE001 — incomplete aggregates must never be returned
            raise EventStoreError(
                "Could not reconstruct aggregate from snapshot or events"
            ) from exc
        return aggregate

    async def save(self, aggregate: TAggregate) -> None:
        """Save an aggregate's pending events.

        This method:
        1. Persists pending events to the event store
        2. Creates a snapshot if policy triggers
        3. Publishes events to the event bus
        4. Clears pending events from the aggregate

        Args:
            aggregate: The aggregate to save

        Raises:
            ConcurrencyError: If version conflict detected
        """
        pending_events = aggregate.get_pending_events()

        if not pending_events:
            return

        stream_id = str(aggregate.id)
        expected_version = aggregate.version - len(pending_events)

        # Use snapshot manager if available
        if self._snapshot_manager:
            # Get current state for potential snapshot
            state = aggregate.model_dump(exclude={"_pending_events", "_is_replaying"})

            await self._snapshot_manager.save_and_maybe_snapshot(
                aggregate_id=stream_id,
                aggregate_type=self._aggregate_type.__name__,
                events=pending_events,
                current_state=state,
                expected_version=expected_version,
            )
        else:
            # Direct save without snapshots
            await self._event_store.append(
                stream_id=stream_id,
                events=pending_events,
                expected_version=expected_version,
            )

        # Publish events if event bus is configured
        if self._event_bus:
            for event in pending_events:
                await self._event_bus.publish(event)

        # Clear pending events
        aggregate.clear_pending_events()

    async def exists(self, aggregate_id: UUID | str) -> bool:
        """Check if an aggregate exists.

        Args:
            aggregate_id: The aggregate identifier

        Returns:
            True if the event stream has a positive logical version. This does
            not establish that the aggregate can be replayed or that a snapshot
            without events exists.
        """
        return await validated_stream_version(self._event_store, str(aggregate_id)) > 0

    async def get_or_raise(self, aggregate_id: UUID | str) -> TAggregate:
        """Get an aggregate or raise an error if not found.

        Args:
            aggregate_id: The aggregate identifier

        Returns:
            The aggregate

        Raises:
            AggregateNotFoundError: If aggregate not found
        """
        aggregate = await self.get(aggregate_id)
        if aggregate is None:
            raise AggregateNotFoundError(
                aggregate_type=self._aggregate_type.__name__,
                aggregate_id=str(aggregate_id),
            )
        return aggregate

    async def force_snapshot(self, aggregate: TAggregate) -> None:
        """Force creation of a snapshot for an aggregate.

        Useful for bulk operations or maintenance.

        Args:
            aggregate: The aggregate to snapshot
        """
        if not self._snapshot_manager:
            return

        if aggregate.get_pending_events():
            raise EventStoreError("Cannot snapshot an aggregate with pending events")
        version = aggregate.version
        aggregate_id = str(aggregate.id)

        def extract_state() -> dict[str, Any]:
            if (
                aggregate.get_pending_events()
                or aggregate.version != version
                or str(aggregate.id) != aggregate_id
            ):
                raise EventStoreError("Aggregate changed while preparing snapshot")
            return aggregate.model_dump(exclude={"_pending_events", "_is_replaying"})

        await self._snapshot_manager.force_snapshot(
            aggregate_id=aggregate_id,
            aggregate_type=self._aggregate_type.__name__,
            state_extractor=extract_state,
            expected_version=version,
        )


__all__ = ["EventSourcingRepository"]
