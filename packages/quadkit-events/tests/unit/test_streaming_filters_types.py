"""Tests for events streaming filters types module."""

import pytest
from datetime import datetime, UTC

from quadkit.events.streaming.filters.types import EventFilter


class TestEventFilter:
    def test_event_filter_empty_matches_all(self) -> None:
        class FakeEvent:
            pass

        filter = EventFilter()
        event = FakeEvent()
        assert filter.matches(event) is True

    def test_event_filter_event_types_match(self) -> None:
        class FakeEvent:
            pass

        filter = EventFilter(event_types=["OrderCreated", "OrderShipped"])

        class OrderCreated:
            pass

        event = OrderCreated()
        assert filter.matches(event) is True

    def test_event_filter_event_types_no_match(self) -> None:
        class OrderCreated:
            pass

        filter = EventFilter(event_types=["OrderCreated"])
        
        class OrderCancelled:
            pass

        event = OrderCancelled()
        assert filter.matches(event) is False

    def test_event_filter_aggregate_id_match(self) -> None:
        class FakeEvent:
            aggregate_id = "order-123"

        filter = EventFilter(aggregate_id="order-123")
        event = FakeEvent()
        assert filter.matches(event) is True

    def test_event_filter_aggregate_id_no_match(self) -> None:
        class FakeEvent:
            aggregate_id = "order-123"

        filter = EventFilter(aggregate_id="order-456")
        event = FakeEvent()
        assert filter.matches(event) is False

    def test_event_filter_aggregate_id_prefix_match(self) -> None:
        class FakeEvent:
            aggregate_id = "order-123-abc"

        filter = EventFilter(aggregate_id_prefix="order-")
        event = FakeEvent()
        assert filter.matches(event) is True

    def test_event_filter_aggregate_id_prefix_no_match(self) -> None:
        class FakeEvent:
            aggregate_id = "order-123"

        filter = EventFilter(aggregate_id_prefix="invoice-")
        event = FakeEvent()
        assert filter.matches(event) is False

    def test_event_filter_aggregate_type_match(self) -> None:
        class FakeEvent:
            aggregate_type = "Order"

        filter = EventFilter(aggregate_type="Order")
        event = FakeEvent()
        assert filter.matches(event) is True

    def test_event_filter_from_timestamp(self) -> None:
        now = datetime.now(UTC)
        filter = EventFilter(from_timestamp=now)

        class FakeEventOld:
            timestamp = now.replace(year=2020)

        class FakeEventNew:
            timestamp = now

        assert filter.matches(FakeEventOld()) is False
        assert filter.matches(FakeEventNew()) is True

    def test_event_filter_to_timestamp(self) -> None:
        now = datetime.now(UTC)
        filter = EventFilter(to_timestamp=now)

        class FakeEventOld:
            timestamp = now.replace(year=2020)

        class FakeEventFuture:
            timestamp = now.replace(year=2030)

        assert filter.matches(FakeEventOld()) is True
        assert filter.matches(FakeEventFuture()) is False

    def test_event_filter_from_version(self) -> None:
        filter = EventFilter(from_version=5)

        class FakeEventV3:
            version = 3

        class FakeEventV7:
            version = 7

        assert filter.matches(FakeEventV3()) is False
        assert filter.matches(FakeEventV7()) is True

    def test_event_filter_to_version(self) -> None:
        filter = EventFilter(to_version=5)

        class FakeEventV3:
            version = 3

        class FakeEventV7:
            version = 7

        assert filter.matches(FakeEventV3()) is True
        assert filter.matches(FakeEventV7()) is False

    def test_event_filter_metadata_match(self) -> None:
        filter = EventFilter(metadata_match={"user_id": "user-123", "env": "prod"})

        class FakeEventMatch:
            metadata = {"user_id": "user-123", "env": "prod"}

        class FakeEventNoMatch:
            metadata = {"user_id": "user-456"}

        class FakeEventNoMetadata:
            pass

        assert filter.matches(FakeEventMatch()) is True
        assert filter.matches(FakeEventNoMatch()) is False
        assert filter.matches(FakeEventNoMetadata()) is False

    def test_event_filter_custom_predicate(self) -> None:
        filter = EventFilter(
            custom_predicate=lambda e: hasattr(e, "amount") and e.amount > 100
        )

        class FakeEventLow:
            amount = 50

        class FakeEventHigh:
            amount = 200

        class FakeEventNoAmount:
            pass

        assert filter.matches(FakeEventLow()) is False
        assert filter.matches(FakeEventHigh()) is True
        assert filter.matches(FakeEventNoAmount()) is False

    def test_event_filter_combined_and(self) -> None:
        filter = EventFilter(
            event_types=["OrderCreated"],
            aggregate_id="order-123",
        )

        class FakeEventMatching:
            pass

        assert filter.matches(FakeEventMatching()) is False

    def test_event_filter_and_operator(self) -> None:
        filter1 = EventFilter(event_types=["OrderCreated"])
        filter2 = EventFilter(aggregate_id="order-123")

        combined = filter1 & filter2

        class FakeEvent:
            pass

        assert combined is not None
        assert hasattr(combined, "filters")

    def test_event_filter_or_operator(self) -> None:
        filter1 = EventFilter(event_types=["OrderCreated"])
        filter2 = EventFilter(event_types=["OrderCancelled"])

        combined = filter1 | filter2

        assert combined is not None
        assert hasattr(combined, "filters")

    def test_event_filter_invert(self) -> None:
        filter = EventFilter(event_types=["OrderCreated"])

        negated = ~filter

        assert negated is not None
        assert hasattr(negated, "inner")
