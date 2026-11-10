"""Tests for the framework's durable channel-neutral delivery worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect

import pytest

from quadkit.contracts.mailer import EmailMessage
from quadkit.contracts.notification.delivery import DeliveryStatus
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.notification.delivery.dispatcher import NotificationDeliveryDispatcher
from quadkit.notification.delivery.mailer_channel import MailerDeliveryChannel
from quadkit.notification.delivery.retry import DeferredRetryMailer
from quadkit.notification.delivery.stores import MemoryDeliveryStore
from quadkit.notification.delivery.worker import flush_retries
from quadkit.primitives import clock
from quadkit.result import Err, Ok


class FlakyBackend:
    """Mail backend failing the first *fail_times* sends."""

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage):
        if self.fail_times > 0:
            self.fail_times -= 1
            self.sent.append(message)
            return Err(RuntimeError("smtp unavailable"))
        self.sent.append(message)
        return Ok("receipt")


def test_deferred_mailer_defaults_match_worker_defaults() -> None:
    """The two halves of the optional mail helper start with one policy."""
    mailer = DeferredRetryMailer(FlakyBackend(), MemoryDeliveryStore())
    worker_parameters = inspect.signature(flush_retries).parameters

    assert mailer.max_retries == worker_parameters["max_attempts"].default
    assert mailer.base_delay == worker_parameters["base_delay"].default


@pytest.mark.asyncio
async def test_flush_delivers_after_transient_failure() -> None:
    """The producer's retry settings align with the generic worker."""
    store = MemoryDeliveryStore()
    clock_impl = _MutableClock()
    backend = FlakyBackend(fail_times=1)
    mailer = DeferredRetryMailer(
        backend, store, max_retries=2, base_delay=10.0
    )
    message = EmailMessage(
        to=["ada@example.com"], subject="Reset", body="Click here"
    )
    dispatcher = NotificationDeliveryDispatcher([MailerDeliveryChannel(backend)])

    with clock.use(clock_impl):
        send_result = await mailer.send(message)  # fails → state persisted as retrying
        assert send_result.is_ok()
        delivery_id = send_result.unwrap()
        record = await store.get_delivery(delivery_id)
        assert record is not None
        assert record.status == DeliveryStatus.RETRYING
        assert record.retry_after == clock_impl.current + timedelta(seconds=10)

        clock_impl.current += timedelta(seconds=10)
        delivered = await flush_retries(
            store,
            dispatcher,
            max_attempts=mailer.max_retries,
            base_delay=mailer.base_delay,
        )

    assert delivered == 1
    assert len(backend.sent) == 2  # initial attempt + retry
    record = await store.get_delivery(delivery_id)
    assert record is not None
    assert record.status == DeliveryStatus.DELIVERED
    assert record.attempts == mailer.max_retries


@pytest.mark.asyncio
async def test_aligned_deferred_retry_policy_dead_letters_at_attempt_limit() -> None:
    """The worker's limit equals the producer's declared total attempts."""
    store = MemoryDeliveryStore()
    clock_impl = _MutableClock()
    backend = FlakyBackend(fail_times=2)
    mailer = DeferredRetryMailer(
        backend, store, max_retries=2, base_delay=10.0
    )
    dispatcher = NotificationDeliveryDispatcher([MailerDeliveryChannel(backend)])
    message = EmailMessage(
        to=["ada@example.com"], subject="Reset", body="Click here"
    )

    with clock.use(clock_impl):
        send_result = await mailer.send(message)
        assert send_result.is_ok()
        delivery_id = send_result.unwrap()
        clock_impl.current += timedelta(seconds=10)
        assert await flush_retries(
            store,
            dispatcher,
            max_attempts=mailer.max_retries,
            base_delay=mailer.base_delay,
        ) == 0

    record = await store.get_delivery(delivery_id)
    assert record is not None
    assert record.status == DeliveryStatus.FAILED
    assert record.attempts == mailer.max_retries
    assert [attempt["attempt_number"] for attempt in store._attempts[delivery_id]] == [1, 2]


@pytest.mark.asyncio
async def test_flush_is_noop_when_nothing_due() -> None:
    store = MemoryDeliveryStore()
    backend = FlakyBackend()
    dispatcher = NotificationDeliveryDispatcher([MailerDeliveryChannel(backend)])

    delivered = await flush_retries(store, dispatcher)

    assert delivered == 0
    assert backend.sent == []


class _MutableClock:
    """Small deterministic clock for retry scheduling and lease tests."""

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


@pytest.mark.asyncio
async def test_worker_retries_with_backoff_then_dead_letters() -> None:
    """Attempt history survives retries and the last error is terminal."""
    store = MemoryDeliveryStore()
    clock_impl = _MutableClock()
    backend = FlakyBackend(fail_times=2)
    dispatcher = NotificationDeliveryDispatcher([MailerDeliveryChannel(backend)])
    with clock.use(clock_impl):
        delivery_id = await store.create_pending(
            DeliveryMessage(
                channel="email",
                recipient="ada@example.com",
                subject="Reset",
                body="Click here",
            )
        )
        assert await flush_retries(
            store, dispatcher, max_attempts=2, base_delay=10, max_delay=30
        ) == 0
        first = await store.get_delivery(delivery_id)
        assert first is not None
        assert first.status == DeliveryStatus.RETRYING
        assert first.retry_after == clock_impl.current + timedelta(seconds=10)
        assert "smtp unavailable" in first.last_error
        assert len(store._attempts[delivery_id]) == 1
        assert store._attempts[delivery_id][0]["outcome"] == "failed"

        clock_impl.current += timedelta(seconds=10)
        assert await flush_retries(
            store, dispatcher, max_attempts=2, base_delay=10, max_delay=30
        ) == 0
        terminal = await store.get_delivery(delivery_id)
        assert terminal is not None
        assert terminal.status == DeliveryStatus.FAILED
        assert terminal.attempts == 2
        assert "smtp unavailable" in terminal.last_error
        assert [attempt["outcome"] for attempt in store._attempts[delivery_id]] == [
            "failed",
            "failed",
        ]


@pytest.mark.asyncio
async def test_expired_worker_lease_can_be_reclaimed() -> None:
    """An abandoned processing row becomes due after the lease expires."""
    store = MemoryDeliveryStore()
    clock_impl = _MutableClock()
    with clock.use(clock_impl):
        delivery_id = await store.create_pending(
            DeliveryMessage(
                channel="email",
                recipient="ada@example.com",
                subject="Reset",
                body="Click here",
            )
        )
        assert await store.claim_delivery(delivery_id, lease_seconds=5)
        assert not await store.claim_delivery(delivery_id, lease_seconds=5)
        clock_impl.current += timedelta(seconds=6)
        due = await store.due_deliveries()
        assert [record.delivery_id for record in due] == [delivery_id]
        assert await store.claim_delivery(delivery_id, lease_seconds=5)
