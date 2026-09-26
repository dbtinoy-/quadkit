import pytest
pytest.skip("async snapshot tests disabled", allow_module_level=True)

import asyncio
from uuid import UUID, uuid4

from quadkit.logging import get_logger
from quadkit.contracts.domain import DomainEvent

# Copy the necessary classes directly to avoid import issues
from quadkit.events.stores import (
    EventCountPolicy,
    InMemoryEventStore,
    InMemorySnapshotStore,
    SnapshotManager,
)

logger = get_logger(__name__)


async def test_snapshot():
    logger.info("Testing snapshot functionality...")

    # Setup
    event_store = InMemoryEventStore()
    snapshot_store = InMemorySnapshotStore()
    manager = SnapshotManager(
        event_store=event_store,
        snapshot_store=snapshot_store,
        policy=EventCountPolicy(3),  # Snapshot every 3 events
    )

    aggregate_id = str(uuid4())  # Use UUID string

    logger.info("Setup complete, creating events...")

    # Simulate saving events
    class MockEvent(DomainEvent):
        value: int

    for i in range(5):
        event = MockEvent(
            aggregate_id=UUID(aggregate_id),
            version=i + 1,
            value=i + 1,
            event_type="TestEvent",
        )

        # Save event
        await manager.save_and_maybe_snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="TestAggregate",
            events=[event],
            current_state={"value": (i + 1)},
            expected_version=i,
        )

        logger.info("Saved event %d, total events: %d", i + 1, i + 1)

    logger.info("Events saved, checking snapshots...")

    # Load with snapshot
    state, events_to_replay, version = await manager.load_with_snapshot(
        aggregate_id=aggregate_id, aggregate_type="TestAggregate",
    )

    logger.info("Snapshot state: %s", state)
    logger.info("Events to replay: %d", len(events_to_replay))
    logger.info("Starting version: %s", version)

    # Calculate final value
    final_value = state["value"] if state else 0
    final_value += len(events_to_replay)

    logger.info("Final aggregate value: %d", final_value)
    logger.info("Snapshot test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_snapshot())
