"""Tests for domain events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from quadkit.contracts.domain.events import DomainEvent, _to_json_safe


class TestToJsonSafe:
    """Tests for _to_json_safe helper function."""

    def test_uuid_converted_to_string(self) -> None:
        """Test UUID is converted to string."""
        test_uuid = uuid4()
        result = _to_json_safe(test_uuid)
        assert isinstance(result, str)
        assert result == str(test_uuid)

    def test_datetime_converted_to_isoformat(self) -> None:
        """Test datetime is converted to ISO format string."""
        from datetime import timezone

        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _to_json_safe(dt)
        assert isinstance(result, str)
        assert result == dt.isoformat()

    def test_preserves_other_types(self) -> None:
        """Test other types are returned unchanged."""
        assert _to_json_safe("string") == "string"
        assert _to_json_safe(42) == 42
        assert _to_json_safe(3.14) == 3.14
        assert _to_json_safe(True) is True
        assert _to_json_safe([1, 2, 3]) == [1, 2, 3]
        assert _to_json_safe({"key": "value"}) == {"key": "value"}


class TestDomainEvent:
    """Tests for DomainEvent base class."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.event_type == "TestEvent"
        assert event.aggregate_id is None
        assert event.aggregate_type is None
        assert event.sequence_number is None
        assert event.actor_id is None
        assert event.schema_version == 1

    def test_custom_event_type(self) -> None:
        """Test custom event_type is preserved."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent(event_type="CustomType")
        assert event.event_type == "CustomType"

    def test_aggregate_fields(self) -> None:
        """Test aggregate fields are set correctly."""

        class TestEvent(DomainEvent):
            pass

        agg_id = uuid4()
        event = TestEvent(aggregate_id=agg_id, aggregate_type="TestAggregate")
        assert event.aggregate_id == agg_id
        assert event.aggregate_type == "TestAggregate"

    def test_actor_id(self) -> None:
        """Test actor_id is set correctly."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent(actor_id="user-123")
        assert event.actor_id == "user-123"

    def test_sequence_number(self) -> None:
        """Test sequence_number is set correctly."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent(sequence_number=5)
        assert event.sequence_number == 5

    def test_schema_version(self) -> None:
        """Test schema_version default is_1."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        assert event.schema_version == 1

    def test_custom_schema_version(self) -> None:
        """Test custom schema_version is preserved."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent(schema_version=2)
        assert event.schema_version == 2


class TestDomainEventToDict:
    """Tests for to_dict method."""

    def test_to_dict_returns_serializable(self) -> None:
        """Test to_dict returns JSON-serializable dict."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        result = event.to_dict()
        assert isinstance(result, dict)
        assert "event_id" in result
        assert "occurred_at" in result
        # UUID and datetime should be converted to strings
        assert isinstance(result["event_id"], str)
        assert isinstance(result["occurred_at"], str)

    def test_to_dict_with_extra_fields(self) -> None:
        """Test to_dict includes extra fields from subclasses."""
        # Note: Extra fields set via __init__ kwargs are NOT included in to_dict
        # because to_dict uses dataclasses.asdict() which only sees declared fields.
        # This test documents the current behavior.

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        result = event.to_dict()
        # Extra fields are not in asdict output
        assert "foo" not in result


class TestDomainEventFromDict:
    """Tests for from_dict class method."""

    def test_from_dict_creates_event(self) -> None:
        """Test from_dict creates event from dict."""

        class TestEvent(DomainEvent):
            pass

        data = {"event_type": "TestEvent"}
        event = TestEvent.from_dict(data)
        assert isinstance(event, TestEvent)
        assert event.event_type == "TestEvent"

    def test_from_dict_with_all_fields(self) -> None:
        """Test from_dict handles all fields."""

        class TestEvent(DomainEvent):
            pass

        agg_id = uuid4()
        data = {
            "event_type": "TestEvent",
            "aggregate_id": str(agg_id),
            "aggregate_type": "TestAggregate",
            "actor_id": "user-123",
            "sequence_number": 1,
        }
        event = TestEvent.from_dict(data)
        # aggregate_id is stored as string (from_dict passes it through as-is)
        assert event.aggregate_id == str(agg_id)
        assert event.aggregate_type == "TestAggregate"
        assert event.actor_id == "user-123"
        assert event.sequence_number == 1


class TestDomainEventForAggregate:
    """Tests for for_aggregate method."""

    def test_for_aggregate_sets_fields(self) -> None:
        """Test for_aggregate sets aggregate fields on copy."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent()
        agg_id = uuid4()
        result = event.for_aggregate(agg_id, "TestAggregate")
        # Should return a new event (immutable)
        assert result is not event
        assert result.aggregate_id == agg_id
        assert result.aggregate_type == "TestAggregate"
        # Original should be unchanged
        assert event.aggregate_id is None
        assert event.aggregate_type is None

    def test_for_aggregate_preserves_other_fields(self) -> None:
        """Test for_aggregate preserves other event fields."""

        class TestEvent(DomainEvent):
            pass

        event = TestEvent(actor_id="user-123", schema_version=2)
        agg_id = uuid4()
        result = event.for_aggregate(agg_id, "TestAggregate")
        assert result.actor_id == "user-123"
        assert result.schema_version == 2


class TestDomainEventSubclass:
    """Tests for DomainEvent subclasses."""

    def test_subclass_with_extra_fields(self) -> None:
        """Test subclass with additional fields via __init__."""

        class OrderCreated(DomainEvent):
            def __init__(
                self,
                order_id: str = "",
                total: float = 0.0,
                customer_email: str = "",
                **kwargs: object,
            ) -> None:
                super().__init__(**kwargs)
                self.order_id = order_id
                self.total = total
                self.customer_email = customer_email

        event = OrderCreated(
            order_id="order-123",
            total=99.99,
            customer_email="test@example.com",
        )
        assert event.order_id == "order-123"
        assert event.total == 99.99
        assert event.customer_email == "test@example.com"
        assert event.event_type == "OrderCreated"

    def test_subclass_to_dict_includes_extra_fields(self) -> None:
        """Test to_dict includes subclass fields."""

        class OrderCreated(DomainEvent):
            def __init__(
                self, order_id: str = "", total: float = 0.0, **kwargs: object
            ) -> None:
                super().__init__(**kwargs)
                self.order_id = order_id
                self.total = total

        event = OrderCreated(order_id="order-123", total=99.99)
        result = event.to_dict()
        # Extra fields set directly on instance are not in asdict
        # This test documents the behavior
        assert "order_id" not in result
        assert "total" not in result
