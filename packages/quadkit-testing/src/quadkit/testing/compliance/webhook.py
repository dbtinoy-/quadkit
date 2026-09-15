from __future__ import annotations

"""Contract compliance suites for webhook protocol implementations.

Covers :class:`~quadkit.contracts.webhook.protocols.WebhookSubscriptionStoreProtocol`
and :class:`~quadkit.contracts.webhook.protocols.WebhookDeliveryStoreProtocol`.
Subclass either compliance class, implement the abstract factory, and pytest
will run all contract checks automatically::

    class TestInMemorySubscriptionStore(WebhookSubscriptionStoreCompliance):
        async def create_store(self):
            return InMemoryWebhookSubscriptionStore()

    class TestInMemoryDeliveryStore(WebhookDeliveryStoreCompliance):
        async def create_store(self):
            return InMemoryWebhookDeliveryStore()
"""

import abc
from datetime import UTC, datetime
from typing import Any
import uuid

import pytest

__all__ = ["WebhookDeliveryStoreCompliance", "WebhookSubscriptionStoreCompliance"]


# ------------------------------------------------------------------
# Test-data helpers — deferred imports keep the module importable
# even in minimal environments.
# ------------------------------------------------------------------


def _make_subscription(**kwargs: Any) -> Any:
    """Build a minimal ``WebhookSubscription`` for compliance tests.

    Args:
        **kwargs: Field overrides applied on top of sensible defaults.

    Returns:
        A ``WebhookSubscription`` ready for store operations.
    """
    from quadkit.contracts.webhook.types import WebhookSubscription

    defaults: dict[str, Any] = {
        "subscription_id": uuid.uuid4().hex,
        "url": f"https://example.com/hooks/{uuid.uuid4().hex[:8]}",
        "secret": uuid.uuid4().hex,
        "active": True,
    }
    defaults.update(kwargs)
    return WebhookSubscription(**defaults)


def _make_attempt(**kwargs: Any) -> Any:
    """Build a minimal ``DeliveryAttempt`` for compliance tests.

    Args:
        **kwargs: Field overrides applied on top of sensible defaults.

    Returns:
        A ``DeliveryAttempt`` ready for store operations.
    """
    from quadkit.contracts.webhook.types import DeliveryAttempt, DeliveryStatus

    defaults: dict[str, Any] = {
        "attempt_id": uuid.uuid4().hex,
        "subscription_id": uuid.uuid4().hex,
        "event_id": uuid.uuid4().hex,
        "event_type": "test.created",
        "status": DeliveryStatus.DELIVERED,
        "status_code": 200,
        "attempt_number": 1,
    }
    defaults.update(kwargs)
    return DeliveryAttempt(**defaults)


# ------------------------------------------------------------------
# WebhookSubscriptionStoreCompliance
# ------------------------------------------------------------------


class WebhookSubscriptionStoreCompliance(abc.ABC):
    """Compliance suite for ``WebhookSubscriptionStoreProtocol`` implementations.

    Subclass and implement :meth:`create_store` to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_store(self) -> Any:
        """Create the subscription store implementation under test.

        Returns:
            A fresh instance implementing ``WebhookSubscriptionStoreProtocol``.
        """
        ...

    # ------------------------------------------------------------------
    # create / get
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_and_get_round_trip(self) -> None:
        """create() persists a subscription retrievable by get()."""
        store = await self.create_store()
        sub = _make_subscription()
        await store.create(sub)
        retrieved = await store.get(sub.subscription_id)
        assert retrieved is not None
        assert retrieved.subscription_id == sub.subscription_id
        assert retrieved.url == sub.url

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        """get() returns None for an unknown subscription_id."""
        store = await self.create_store()
        result = await store.get(uuid.uuid4().hex)
        assert result is None

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_includes_created_subscription(self) -> None:
        """list() returns subscriptions that were created."""
        store = await self.create_store()
        sub = _make_subscription()
        await store.create(sub)
        results = await store.list(active_only=False)
        assert isinstance(results, list)
        ids = [s.subscription_id for s in results]
        assert sub.subscription_id in ids

    @pytest.mark.asyncio
    async def test_list_active_only_excludes_inactive(self) -> None:
        """list(active_only=True) excludes inactive subscriptions."""
        store = await self.create_store()
        active_sub = _make_subscription(active=True)
        inactive_sub = _make_subscription(active=False)
        await store.create(active_sub)
        await store.create(inactive_sub)
        results = await store.list(active_only=True)
        ids = [s.subscription_id for s in results]
        assert active_sub.subscription_id in ids
        assert inactive_sub.subscription_id not in ids

    @pytest.mark.asyncio
    async def test_list_returns_empty_list_when_empty(self) -> None:
        """list() returns an empty list when no subscriptions exist."""
        store = await self.create_store()
        results = await store.list(active_only=False)
        assert isinstance(results, list)

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_persists_changes(self) -> None:
        """update() persists changes to an existing subscription."""
        from quadkit.contracts.webhook.types import WebhookSubscription

        store = await self.create_store()
        sub = _make_subscription(active=True)
        await store.create(sub)
        deactivated = WebhookSubscription(
            subscription_id=sub.subscription_id,
            url=sub.url,
            secret=sub.secret,
            active=False,
        )
        await store.update(deactivated)
        retrieved = await store.get(sub.subscription_id)
        assert retrieved is not None
        assert retrieved.active is False

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_removes_subscription(self) -> None:
        """delete() removes a subscription so get() returns None afterwards."""
        store = await self.create_store()
        sub = _make_subscription()
        await store.create(sub)
        await store.delete(sub.subscription_id)
        result = await store.get(sub.subscription_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_does_not_raise(self) -> None:
        """delete() on an unknown ID completes without raising."""
        store = await self.create_store()
        await store.delete(uuid.uuid4().hex)


# ------------------------------------------------------------------
# WebhookDeliveryStoreCompliance
# ------------------------------------------------------------------


class WebhookDeliveryStoreCompliance(abc.ABC):
    """Compliance suite for ``WebhookDeliveryStoreProtocol`` implementations.

    Subclass and implement :meth:`create_store` to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_store(self) -> Any:
        """Create the delivery store implementation under test.

        Returns:
            A fresh instance implementing ``WebhookDeliveryStoreProtocol``.
        """
        ...

    # ------------------------------------------------------------------
    # record_attempt
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_record_attempt_does_not_raise(self) -> None:
        """record_attempt() completes without raising for a valid attempt."""
        store = await self.create_store()
        await store.record_attempt(_make_attempt())

    # ------------------------------------------------------------------
    # get_attempts
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_attempts_returns_recorded(self) -> None:
        """get_attempts() returns attempts that were recorded."""
        store = await self.create_store()
        sub_id = uuid.uuid4().hex
        attempt = _make_attempt(subscription_id=sub_id)
        await store.record_attempt(attempt)
        results = await store.get_attempts(subscription_id=sub_id)
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(a.attempt_id == attempt.attempt_id for a in results)

    @pytest.mark.asyncio
    async def test_get_attempts_filters_by_subscription(self) -> None:
        """get_attempts() filters results to the requested subscription_id."""
        store = await self.create_store()
        sub_a = uuid.uuid4().hex
        sub_b = uuid.uuid4().hex
        await store.record_attempt(_make_attempt(subscription_id=sub_a))
        await store.record_attempt(_make_attempt(subscription_id=sub_b))
        results = await store.get_attempts(subscription_id=sub_a)
        assert all(a.subscription_id == sub_a for a in results)

    @pytest.mark.asyncio
    async def test_get_attempts_returns_empty_list_for_unknown(self) -> None:
        """get_attempts() returns an empty list for an unknown subscription."""
        store = await self.create_store()
        results = await store.get_attempts(subscription_id=uuid.uuid4().hex)
        assert isinstance(results, list)
        assert len(results) == 0

    # ------------------------------------------------------------------
    # count_recent_failures
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_recent_failures_counts_failed_attempts(self) -> None:
        """count_recent_failures() counts FAILED attempts since a given time."""
        from quadkit.contracts.webhook.types import DeliveryStatus

        store = await self.create_store()
        sub_id = uuid.uuid4().hex
        since = datetime(2000, 1, 1, tzinfo=UTC)
        await store.record_attempt(
            _make_attempt(subscription_id=sub_id, status=DeliveryStatus.FAILED)
        )
        await store.record_attempt(
            _make_attempt(subscription_id=sub_id, status=DeliveryStatus.FAILED)
        )
        count = await store.count_recent_failures(sub_id, since)
        assert count >= 2

    @pytest.mark.asyncio
    async def test_count_recent_failures_returns_zero_for_unknown(self) -> None:
        """count_recent_failures() returns 0 for a subscription with no failures."""
        store = await self.create_store()
        since = datetime(2000, 1, 1, tzinfo=UTC)
        count = await store.count_recent_failures(uuid.uuid4().hex, since)
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_recent_failures_ignores_delivered(self) -> None:
        """count_recent_failures() does not count DELIVERED attempts."""
        from quadkit.contracts.webhook.types import DeliveryStatus

        store = await self.create_store()
        sub_id = uuid.uuid4().hex
        since = datetime(2000, 1, 1, tzinfo=UTC)
        await store.record_attempt(
            _make_attempt(subscription_id=sub_id, status=DeliveryStatus.DELIVERED)
        )
        count = await store.count_recent_failures(sub_id, since)
        assert count == 0

    # ------------------------------------------------------------------
    # get_dead_letters
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_dead_letters_returns_dead_lettered_attempts(self) -> None:
        """get_dead_letters() returns attempts in DEAD_LETTER status."""
        from quadkit.contracts.webhook.types import DeliveryStatus

        store = await self.create_store()
        sub_id = uuid.uuid4().hex
        dead = _make_attempt(subscription_id=sub_id, status=DeliveryStatus.DEAD_LETTER)
        await store.record_attempt(dead)
        results = await store.get_dead_letters(subscription_id=sub_id)
        assert isinstance(results, list)
        assert any(a.attempt_id == dead.attempt_id for a in results)

    @pytest.mark.asyncio
    async def test_get_dead_letters_excludes_delivered(self) -> None:
        """get_dead_letters() does not return DELIVERED attempts."""
        from quadkit.contracts.webhook.types import DeliveryStatus

        store = await self.create_store()
        sub_id = uuid.uuid4().hex
        delivered = _make_attempt(
            subscription_id=sub_id, status=DeliveryStatus.DELIVERED
        )
        await store.record_attempt(delivered)
        results = await store.get_dead_letters(subscription_id=sub_id)
        assert all(a.attempt_id != delivered.attempt_id for a in results)

    @pytest.mark.asyncio
    async def test_get_dead_letters_returns_empty_list_when_none(self) -> None:
        """get_dead_letters() returns an empty list when no dead letters exist."""
        store = await self.create_store()
        results = await store.get_dead_letters(subscription_id=uuid.uuid4().hex)
        assert isinstance(results, list)
        assert len(results) == 0
