"""Regression tests for the framework SQL notification outbox."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from quadkit.contracts.notification.delivery import (
    DeliveryStatus,
    DeliveryStoreProtocol,
)
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.notification.delivery.stores import MemoryDeliveryStore, SqlDeliveryStore
from quadkit.primitives import clock
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.fixture
async def store():
    """SqlDeliveryStore over an in-memory SQLite provider."""
    provider = SQLiteProvider(database_path=":memory:")
    await provider.connect()
    try:
        yield SqlDeliveryStore(provider)
    finally:
        await provider.connection_manager.disconnect()


class _MutableClock:
    """Deterministic UTC clock for persistence/backoff tests."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.current.timestamp()

    def timestamp(self) -> float:
        return self.current.timestamp()

    def time(self) -> float:
        return self.current.timestamp()


def test_memory_and_sql_stores_match_the_delivery_store_contract(store) -> None:
    """Both concrete stores expose the complete public outbox protocol."""
    assert isinstance(MemoryDeliveryStore(), DeliveryStoreProtocol)
    assert isinstance(store, DeliveryStoreProtocol)


@pytest.mark.asyncio
async def test_create_pending_persists_channel_neutral_message(store) -> None:
    """The outbox round-trips channel, body and metadata through SQL."""
    message = DeliveryMessage(
        channel="email",
        recipient="a@example.com",
        subject="Hello",
        body="World",
        metadata={"announcement_id": 7},
    )
    delivery_id = await store.create_pending(message)

    rows = await store.due_deliveries()
    assert len(rows) == 1
    record = rows[0]
    assert record.delivery_id == delivery_id
    assert record.message.channel == "email"
    assert record.message.recipient == "a@example.com"
    assert record.message.subject == "Hello"
    assert record.message.body == "World"
    assert record.message.metadata == {"announcement_id": 7}
    assert record.status == DeliveryStatus.PENDING

    fetched = await store.get_delivery(delivery_id)
    assert fetched == record


@pytest.mark.asyncio
async def test_mark_delivered_updates_row(store) -> None:
    """mark_delivered applies against the stored row and releases its lease."""
    delivery_id = await store.create_pending(
        DeliveryMessage(
            channel="email",
            recipient="b@example.com",
            subject="S",
            body="B",
        )
    )
    assert await store.claim_delivery(delivery_id, lease_seconds=30)
    await store.mark_delivered(delivery_id)

    record = await store.get_delivery(delivery_id)
    assert record is not None
    assert record.status == DeliveryStatus.DELIVERED
    result = await store._db.execute_query(  # noqa: SLF001 — test-only lease detail
        "SELECT lease_until FROM notification_delivery_state WHERE delivery_id = ?",
        [delivery_id],
    )
    assert result.rows[0]["lease_until"] is None


@pytest.mark.asyncio
async def test_failed_attempt_error_is_persisted_on_delivery(store) -> None:
    """The current failure remains visible between retries and after reload."""
    delivery_id = await store.create_pending(
        DeliveryMessage(
            channel="slack",
            recipient="https://hooks.slack.com/services/test",
            subject="Alert",
            body="CPU hot",
        )
    )
    assert await store.claim_delivery(delivery_id)
    await store.record_attempt(
        delivery_id, "https://hooks.slack.com/services/test", "Alert", 1
    )
    await store.complete_attempt(
        delivery_id,
        1,
        outcome="failed",
        error="HTTP 503",
    )
    await store.schedule_retry(delivery_id, delay_seconds=60)

    record = await store.get_delivery(delivery_id)
    assert record is not None
    assert record.status == DeliveryStatus.RETRYING
    assert record.attempts == 1
    assert record.last_error == "HTTP 503"
    assert record.retry_after is not None


@pytest.mark.asyncio
async def test_retry_attempts_and_dead_letter_survive_store_restart(tmp_path) -> None:
    """The SQL outbox preserves retry state, history, and terminal status."""
    db_path = tmp_path / "notification-outbox.sqlite"
    clock_impl = _MutableClock()
    delivery_id = ""
    with clock.use(clock_impl):
        first_provider = SQLiteProvider(database_path=str(db_path))
        await first_provider.connect()
        first_store = SqlDeliveryStore(first_provider)
        try:
            delivery_id = await first_store.create_pending(
                DeliveryMessage(
                    channel="slack",
                    recipient="https://hooks.slack.com/services/test",
                    subject="Alert",
                    body="CPU hot",
                )
            )
            assert await first_store.claim_delivery(delivery_id)
            await first_store.record_attempt(
                delivery_id,
                "https://hooks.slack.com/services/test",
                "Alert",
                1,
            )
            await first_store.complete_attempt(
                delivery_id, 1, outcome="failed", error="HTTP 503"
            )
            await first_store.schedule_retry(delivery_id, delay_seconds=30)
        finally:
            await first_provider.connection_manager.disconnect()

        second_provider = SQLiteProvider(database_path=str(db_path))
        await second_provider.connect()
        second_store = SqlDeliveryStore(second_provider)
        try:
            retrying = await second_store.get_delivery(delivery_id)
            assert retrying is not None
            assert retrying.status == DeliveryStatus.RETRYING
            assert retrying.attempts == 1
            assert retrying.last_error == "HTTP 503"
            assert retrying.retry_after == clock_impl.current + timedelta(seconds=30)
            assert await second_store.due_deliveries() == []

            clock_impl.current += timedelta(seconds=30)
            due = await second_store.due_deliveries()
            assert [record.delivery_id for record in due] == [delivery_id]
            assert await second_store.claim_delivery(delivery_id)
            await second_store.record_attempt(
                delivery_id,
                "https://hooks.slack.com/services/test",
                "Alert",
                2,
            )
            await second_store.complete_attempt(
                delivery_id, 2, outcome="failed", error="HTTP 503 again"
            )
            await second_store.mark_failed(delivery_id, reason="HTTP 503 again")
            attempts = await second_provider.execute_query(
                "SELECT attempt_number, outcome, error "
                "FROM notification_delivery_state_attempts "
                "WHERE delivery_id = ? ORDER BY attempt_number",
                [delivery_id],
            )
            assert [row["attempt_number"] for row in attempts.rows] == [1, 2]
            assert [row["outcome"] for row in attempts.rows] == ["failed", "failed"]
            assert attempts.rows[0]["error"] == "HTTP 503"
        finally:
            await second_provider.connection_manager.disconnect()

        third_provider = SQLiteProvider(database_path=str(db_path))
        await third_provider.connect()
        third_store = SqlDeliveryStore(third_provider)
        try:
            dead_letter = await third_store.get_delivery(delivery_id)
            assert dead_letter is not None
            assert dead_letter.status == DeliveryStatus.FAILED
            assert dead_letter.attempts == 2
            assert dead_letter.last_error == "HTTP 503 again"
        finally:
            await third_provider.connection_manager.disconnect()


@pytest.mark.asyncio
async def test_claim_is_atomic_for_competing_workers(store) -> None:
    """Exactly one worker can acquire a fresh row's lease."""
    delivery_id = await store.create_pending(
        DeliveryMessage(
            channel="email",
            recipient="c@example.com",
            subject="S",
            body="B",
        )
    )
    results = await asyncio.gather(
        store.claim_delivery(delivery_id),
        store.claim_delivery(delivery_id),
    )
    assert sorted(results) == [False, True]


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-16T00:00:00",
        datetime(2026, 10, 16),
        "2026-10-16T00:00:00+00:00",
        datetime(2026, 10, 16, tzinfo=UTC),
        "2026-10-16T08:00:00+08:00",
        datetime.fromisoformat("2026-10-15T19:00:00-05:00"),
    ],
)
def test_sql_delivery_timestamp_hydration_restores_utc(timestamp) -> None:
    """SQL naive-UTC binding and offset-aware drivers hydrate the same instant."""
    record = SqlDeliveryStore._row_to_record(  # noqa: SLF001
        {
            "delivery_id": "codec-probe",
            "recipient": "fixture@example.invalid",
            "created_at": timestamp,
            "retry_after": timestamp,
        }
    )
    expected = datetime(2026, 10, 16, tzinfo=UTC)
    assert record.created_at == expected
    assert record.created_at.tzinfo is UTC
    assert record.retry_after == expected
    assert record.retry_after.tzinfo is UTC


@pytest.mark.parametrize("timestamp", [None, "not-a-timestamp", ""])
def test_sql_delivery_invalid_timestamp_fallback_is_preserved(timestamp) -> None:
    """Absent/malformed retry times remain absent; creation retains clock fallback."""
    clock_impl = _MutableClock()
    with clock.use(clock_impl):
        record = SqlDeliveryStore._row_to_record(  # noqa: SLF001
            {
                "delivery_id": "codec-probe",
                "recipient": "fixture@example.invalid",
                "created_at": timestamp,
                "retry_after": timestamp,
            }
        )
    assert record.created_at == clock_impl.current
    assert record.retry_after is None
