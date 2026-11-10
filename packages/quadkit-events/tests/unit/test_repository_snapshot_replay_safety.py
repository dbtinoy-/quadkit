"""Snapshot-backed aggregate replay must not return incomplete state."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.aggregates import AggregateRoot
from quadkit.events.exceptions import EventStoreError
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.stores.sqlite.snapshot_store import SqliteSnapshotStore
from quadkit.events.types import Snapshot
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class FundsAdded(DomainEvent):
    amount: int


class Unhandled(DomainEvent):
    amount: int


class Account(AggregateRoot):
    balance: int = 0

    def _handle_funds_added(self, event):
        if event.amount < 0:
            raise ValueError("invalid private event detail")
        self.balance += event.amount

    def add(self, amount):
        self._apply(FundsAdded(aggregate_id=self.id, amount=amount))


async def open_sqlite(path, pooled):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    db = SQLiteProvider(str(path), connection_pool=pool)
    await db.connect()
    events = SqliteEventStore(provider=db)
    snapshots = SqliteSnapshotStore(provider=db)
    await events.connect()
    await snapshots.connect()
    events.register_event_type("FundsAdded", FundsAdded)
    events.register_event_type("Unhandled", Unhandled)
    return db, events, snapshots


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_sqlite_snapshot_replay_retains_identity_version_and_allows_save(
    tmp_path, pooled
):
    path = tmp_path / "aggregate.sqlite"
    db, events, snapshots = await open_sqlite(path, pooled)
    aggregate_id = uuid4()
    try:
        await events.append(
            str(aggregate_id),
            [
                FundsAdded(aggregate_id=aggregate_id, amount=1),
                FundsAdded(aggregate_id=aggregate_id, amount=2),
            ],
        )
        await snapshots.save_snapshot(
            Snapshot(
                aggregate_id=aggregate_id,
                aggregate_type="Account",
                version=2,
                state={"id": str(aggregate_id), "version": 2, "balance": 3},
            )
        )
        await events.append(
            str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=4)]
        )
    finally:
        await db.disconnect()
    db, events, snapshots = await open_sqlite(path, pooled)
    try:
        repo = EventSourcingRepository(Account, events, snapshots)
        aggregate = await repo.get(aggregate_id)
        assert isinstance(aggregate.id, UUID)
        assert aggregate.id == aggregate_id
        assert aggregate.version == 3
        assert aggregate.balance == 7
        assert aggregate.get_pending_events() == []
        aggregate.add(5)
        await repo.save(aggregate)
        assert await events.get_stream_version(str(aggregate_id)) == 4
        reloaded = await repo.get(aggregate_id)
        assert reloaded.id == aggregate_id
        assert reloaded.version == 4
        assert reloaded.balance == 12
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_no_snapshot_replay_preserves_requested_identity():
    events = InMemoryEventStore()
    aggregate_id = uuid4()
    await events.append(
        str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=3)]
    )
    aggregate = await EventSourcingRepository(Account, events).get(aggregate_id)
    assert aggregate.id == aggregate_id
    assert aggregate.version == 1
    assert aggregate.balance == 3


@pytest.mark.asyncio
async def test_empty_snapshot_is_found_and_uses_snapshot_version():
    events, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    aggregate_id = uuid4()
    await events.append(
        str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=1)]
    )
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id, aggregate_type="Account", version=1, state={}
        )
    )
    aggregate = await EventSourcingRepository(Account, events, snapshots).get(
        aggregate_id
    )
    assert aggregate.id == aggregate_id
    assert aggregate.version == 1
    assert aggregate.balance == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "problem",
    [
        "unknown_field",
        "private_field",
        "version_mismatch",
        "id_mismatch",
        "type_mismatch",
        "handler_failure",
        "unhandled_event",
        "foreign_event",
    ],
)
async def test_snapshot_or_replay_failure_does_not_return_partial_aggregate(problem):
    events, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    aggregate_id = uuid4()
    await events.append(
        str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=1)]
    )
    state = {"id": str(aggregate_id), "version": 1, "balance": 1}
    snapshot_type = "Account"
    if problem == "unknown_field":
        state["missing_field"] = "should not disappear"
    elif problem == "private_field":
        state["_secret_state"] = "should not disappear"
    elif problem == "version_mismatch":
        state["version"] = 99
    elif problem == "id_mismatch":
        state["id"] = str(uuid4())
    elif problem == "type_mismatch":
        snapshot_type = "AnotherAggregate"
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type=snapshot_type,
            version=1,
            state=state,
        )
    )
    if problem == "handler_failure":
        await events.append(
            str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=-1)]
        )
    elif problem == "unhandled_event":
        await events.append(
            str(aggregate_id), [Unhandled(aggregate_id=aggregate_id, amount=1)]
        )
    elif problem == "foreign_event":
        await events.append(
            str(aggregate_id), [FundsAdded(aggregate_id=uuid4(), amount=1)]
        )
    with pytest.raises(EventStoreError):
        await EventSourcingRepository(Account, events, snapshots).get(aggregate_id)


@pytest.mark.asyncio
async def test_unregistered_sqlite_event_type_is_not_replayed_as_generic(tmp_path):
    db, events, snapshots = await open_sqlite(tmp_path / "unknown.sqlite", False)
    aggregate_id = uuid4()
    try:
        await events.append(
            str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=2)]
        )
        events.serializer._event_type_registry.clear()
        with pytest.raises(EventStoreError):
            await EventSourcingRepository(Account, events, snapshots).get(aggregate_id)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_custom_apply_can_handle_nonconventional_events():
    class CustomAccount(Account):
        def _apply(self, event, is_new=True):
            if isinstance(event, Unhandled):
                self.balance += event.amount
            else:
                super()._apply(event, is_new=is_new)

    events = InMemoryEventStore()
    aggregate_id = uuid4()
    await events.append(
        str(aggregate_id), [Unhandled(aggregate_id=aggregate_id, amount=8)]
    )
    aggregate = await EventSourcingRepository(CustomAccount, events).get(aggregate_id)
    assert aggregate.id == aggregate_id
    assert aggregate.balance == 8
    assert aggregate.version == 1


@pytest.mark.asyncio
async def test_snapshot_store_returning_another_aggregate_is_rejected():
    requested, other = uuid4(), uuid4()

    class WrongOwnerSnapshot(InMemorySnapshotStore):
        async def get_latest(self, aggregate_id):
            return Snapshot(
                aggregate_id=other, aggregate_type="Account", version=1, state={}
            )

    repository = EventSourcingRepository(
        Account, InMemoryEventStore(), WrongOwnerSnapshot()
    )
    with pytest.raises(EventStoreError, match="Snapshot identity"):
        await repository.get(requested)


@pytest.mark.asyncio
async def test_non_snapshot_handler_failure_does_not_return_partial_aggregate():
    events = InMemoryEventStore()
    aggregate_id = uuid4()
    await events.append(
        str(aggregate_id), [FundsAdded(aggregate_id=aggregate_id, amount=-1)]
    )
    with pytest.raises(EventStoreError, match="Could not reconstruct aggregate"):
        await EventSourcingRepository(Account, events).get(aggregate_id)
