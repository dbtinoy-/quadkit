"""Scenario tests for the projection manager over real stores.

Drives ``ProjectionManager`` against the real ``InMemoryEventStore`` and
``InMemoryCheckpointStore``: dependency-ordered event distribution with
per-event checkpointing, full rebuilds with idempotent skipping,
crash-mid-rebuild resume from the last checkpoint, pause/error/reset
lifecycle, and ``rebuild_all`` aggregation.
"""

from __future__ import annotations

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.projections.base import (
    ProjectionProtocol,
    ProjectionStatus,
    event_handler,
)
from quadkit.events.projections.manager import (
    ProjectionBuildError,
    ProjectionManager,
    ProjectionNotFoundError,
    ProjectionRebuildError,
)
from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
from quadkit.events.stores.memory import InMemoryEventStore


class OrderCreated(Event):
    order_id: str = "o1"


class OrderShipped(Event):
    order_id: str = "o1"


class OrdersProjection(ProjectionProtocol):
    """Read model of individual orders."""

    def __init__(self) -> None:
        super().__init__()
        self.orders: dict[str, str] = {}
        self.reset_calls = 0

    @property
    def name(self) -> str:
        return "orders"

    @property
    def handles(self) -> set[type]:
        return {OrderCreated, OrderShipped}

    @event_handler(OrderCreated)
    async def on_created(self, event: OrderCreated) -> None:
        self.orders[event.order_id] = "pending"

    @event_handler(OrderShipped)
    async def on_shipped(self, event: OrderShipped) -> None:
        self.orders[event.order_id] = "shipped"

    async def reset(self) -> None:
        self.orders.clear()
        self.reset_calls += 1


class SummaryProjection(ProjectionProtocol):
    """Aggregate order count; depends on the orders projection."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    @property
    def name(self) -> str:
        return "summary"

    @property
    def handles(self) -> set[type]:
        return {OrderCreated}

    @property
    def depends_on(self) -> list[str]:
        return ["orders"]

    @event_handler(OrderCreated)
    async def on_created(self, event: OrderCreated) -> None:
        self.count += 1

    async def reset(self) -> None:
        self.count = 0


async def _seed_events() -> InMemoryEventStore:
    """Append the canonical event sequence; returns the store."""
    store = InMemoryEventStore()
    events = [
        OrderCreated(order_id="o1"),
        OrderShipped(order_id="o1"),
        OrderCreated(order_id="o2"),
        OrderShipped(order_id="o2"),
        OrderCreated(order_id="o3"),
    ]
    for event in events:
        await store.append("orders", [event])
    return store


async def test_process_dependency_order_and_checkpoints() -> None:
    """Events flow in topological order and checkpoints advance per event."""
    store = await _seed_events()
    checkpoint_store = InMemoryCheckpointStore()
    manager = ProjectionManager(event_store=store, checkpoint_store=checkpoint_store)

    orders = OrdersProjection()
    summary = SummaryProjection()
    manager.register(orders)
    manager.register(summary)

    async for event in store.stream_all():
        position = event.sequence_number or 0
        processed = await manager.process(event, position)
        if type(event) is OrderCreated:
            # dependency order: "orders" before "summary"
            assert processed.index("orders") < processed.index("summary")
        else:
            assert processed == ["orders"]

    assert orders.orders == {
        "o1": "shipped",
        "o2": "shipped",
        "o3": "pending",
    }
    assert summary.count == 3

    # checkpoints persisted in both the manager cache and the checkpoint store
    assert await checkpoint_store.get_checkpoint("orders") == 5
    assert await checkpoint_store.get_checkpoint("summary") == 5
    status = manager.get_status("orders")
    assert status is not None
    assert status["position"] == 5
    assert status["status"] == ProjectionStatus.RUNNING.value


async def test_full_rebuild_resets_and_reapplies() -> None:
    """A full rebuild resets state and replays the whole history."""
    store = await _seed_events()
    manager = ProjectionManager(event_store=store)
    orders = OrdersProjection()
    manager.register(orders)

    # first pass
    async for event in store.stream_all():
        await manager.process(event, event.sequence_number or 0)
    assert orders.orders == {"o1": "shipped", "o2": "shipped", "o3": "pending"}

    # full rebuild
    count = await manager.rebuild("orders")
    assert count == 5
    assert orders.reset_calls == 1
    assert orders.status is ProjectionStatus.RUNNING
    assert orders.orders == {"o1": "shipped", "o2": "shipped", "o3": "pending"}
    assert orders.position == 5

    # replaying an old event is idempotently skipped
    async def _first():
        async for e in store.stream_all():
            return e

    first = await _first()
    orders.orders["o1"] = "tampered"
    await manager.process(first, first.sequence_number or 0)
    assert orders.orders["o1"] == "tampered"  # unchanged: skip, not re-apply


async def test_rebuild_crash_resume_from_checkpoint() -> None:
    """A crash mid-rebuild resumes from the last per-event checkpoint."""
    store = await _seed_events()
    manager = ProjectionManager(event_store=store)

    class FlakyProjection(ProjectionProtocol):
        """Crashes exactly once, on the OrderCreated event for order o2."""

        def __init__(self) -> None:
            super().__init__()
            self.seen: list[str] = []
            self.fail_on_order = "o2"

        @property
        def name(self) -> str:
            return "flaky"

        @property
        def handles(self) -> set[type]:
            return {OrderCreated, OrderShipped}

        @event_handler(OrderCreated)
        async def on_created(self, event: OrderCreated) -> None:
            if self.fail_on_order is not None and event.order_id == self.fail_on_order:
                self.fail_on_order = None
                raise ValueError("simulated crash")
            self.seen.append(event.order_id)

        @event_handler(OrderShipped)
        async def on_shipped(self, event: OrderShipped) -> None:
            self.seen.append(event.order_id)

        async def reset(self) -> None:
            self.seen.clear()

    flaky = FlakyProjection()
    manager.register(flaky)

    with pytest.raises(ProjectionRebuildError):
        await manager.rebuild("flaky")
    assert flaky.status is ProjectionStatus.ERROR
    # the checkpoint holds the last event that applied successfully
    # (positions 1-2: o1 created + o1 shipped)
    assert flaky.position == 2

    # resume from the last checkpoint — only the remaining events replay
    count = await manager.resume_rebuild("flaky")
    assert count == 3
    assert flaky.status is ProjectionStatus.RUNNING
    # o1 events applied in the first pass; o2/o3 on the resumed pass
    assert flaky.seen == ["o1", "o1", "o2", "o2", "o3"]
    assert flaky.position == 5


async def test_pause_error_and_reset_lifecycle() -> None:
    """Pause skips processing; errors isolate; reset_all zeroes state."""
    store = await _seed_events()
    manager = ProjectionManager(event_store=store)

    class ExplodingProjection(ProjectionProtocol):
        @property
        def name(self) -> str:
            return "exploding"

        @property
        def handles(self) -> set[type]:
            return {OrderShipped}

        @event_handler(OrderShipped)
        async def on_shipped(self, event: OrderShipped) -> None:
            msg = "projection exploded"
            raise RuntimeError(msg)

        async def reset(self) -> None:
            pass

    orders = OrdersProjection()
    exploding = ExplodingProjection()
    manager.register(orders)
    manager.register(exploding)

    # pause: orders skipped while paused
    assert manager.pause("orders") is True
    async def _first_created():
        async for e in store.stream_all():
            if type(e) is OrderCreated:
                return e

    first = await _first_created()
    processed = await manager.process(first, first.sequence_number or 0)
    assert "orders" not in processed
    assert manager.resume("orders") is True

    # error: a failing projection is isolated and marked ERROR
    async def _first_shipped():
        async for e in store.stream_all():
            if type(e) is OrderShipped:
                return e

    shipped = await _first_shipped()
    position = shipped.sequence_number or 0
    # reset positions first so the event is not idempotently skipped
    await manager.reset_all()
    with pytest.raises(ProjectionBuildError, match="exploded"):
        await manager.process(shipped, position)
    status = manager.get_status("exploding")
    assert status is not None
    assert status["status"] == ProjectionStatus.ERROR.value
    assert "exploded" in (status["error"] or "")
    # the errored projection no longer processes events
    assert "exploding" not in await manager.process(shipped, position)

    # reset_all zeroes every projection and checkpoint
    await manager.reset_all()
    for projection in manager.get_all():
        assert projection.position == 0


async def test_rebuild_all_aggregates_failures() -> None:
    """rebuild_all reports per-projection counts, -1 for failures."""
    store = await _seed_events()
    manager = ProjectionManager(event_store=store)
    manager.register(OrdersProjection())

    class BrokenProjection(ProjectionProtocol):
        @property
        def name(self) -> str:
            return "broken"

        @property
        def handles(self) -> set[type]:
            return {OrderCreated}

        @event_handler(OrderCreated)
        async def on_created(self, event: OrderCreated) -> None:
            msg = "always broken"
            raise TypeError(msg)

        async def reset(self) -> None:
            pass

    manager.register(BrokenProjection())

    results = await manager.rebuild_all()
    assert results["orders"] == 5
    assert results["broken"] == -1

    with pytest.raises(ProjectionNotFoundError):
        await manager.rebuild("no-such-projection")
    manager_no_store = ProjectionManager()
    manager_no_store.register(OrdersProjection())
    with pytest.raises(ProjectionRebuildError, match="No event store"):
        await manager_no_store.rebuild("orders")
