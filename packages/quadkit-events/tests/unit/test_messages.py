"""Unit tests for quadkit-events message types."""

from __future__ import annotations

from uuid import UUID, uuid4
import pytest

from quadkit.events.messages import Command, Event, IdempotentCommand, IntegrationEvent, PaginatedQuery, PagedResult, Query


class TestEvent:
    """Tests for Event message type."""

    def test_event_creation(self) -> None:
        """Test creating an Event."""
        event = Event(
            event_type="UserCreated",
            payload={"user_id": "123", "email": "test@example.com"},
        )

        assert event.event_type == "UserCreated"
        assert event.payload["user_id"] == "123"

    def test_event_with_version(self) -> None:
        """Test Event with version."""
        event = Event(
            event_type="OrderPlaced",
            payload={"order_id": "456"},
            version=1,
        )

        assert event.version == 1

    def test_event_with_version_method(self) -> None:
        """Test with_version method."""
        event = Event(
            event_type="OrderPlaced",
            payload={"order_id": "456"},
            version=1,
        )

        v2_event = event.with_version(2)

        assert v2_event.version == 2

    def test_event_for_aggregate(self) -> None:
        """Test for_aggregate method."""
        aggregate_id = uuid4()
        event = Event(
            event_type="OrderPlaced",
            payload={"order_id": "456"},
        )

        aggregate_event = event.for_aggregate(aggregate_id, "Order")

        assert aggregate_event.aggregate_id == aggregate_id
        assert aggregate_event.aggregate_type == "Order"

    def test_event_with_correlation(self) -> None:
        """Test Event with correlation and causation IDs."""
        correlation_id = uuid4()
        causation_id = uuid4()

        event = Event(
            event_type="OrderPlaced",
            payload={"order_id": "456"},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

        assert event.correlation_id == correlation_id
        assert event.causation_id == causation_id


class TestIntegrationEvent:
    """Tests for IntegrationEvent."""

    def test_integration_event_creation(self) -> None:
        """Test creating an IntegrationEvent."""
        # IntegrationEvent adds source_service and destination_services to Event
        event = IntegrationEvent(
            event_type="UserSignedUp",
            source_service="auth-service",
            destination_services=["notification-service", "analytics-service"],
        )

        assert event.event_type == "UserSignedUp"
        assert event.source_service == "auth-service"
        assert "notification-service" in event.destination_services
        assert "analytics-service" in event.destination_services


class TestCommand:
    """Tests for Command message type."""

    def test_command_creation(self) -> None:
        """Test creating a Command."""
        command = Command()

        assert command is not None

    def test_command_for_aggregate(self) -> None:
        """Test targeting command to aggregate."""
        aggregate_id = uuid4()
        command = Command()

        targeted = command.for_aggregate(aggregate_id, version=5)

        assert targeted.target_aggregate_id == aggregate_id
        assert targeted.expected_version == 5


class TestIdempotentCommand:
    """Tests for IdempotentCommand."""

    def test_idempotent_command_creation(self) -> None:
        """Test creating an IdempotentCommand."""
        command = IdempotentCommand(
            idempotency_key="unique-key-123",
        )

        assert command.idempotency_key == "unique-key-123"


class TestQuery:
    """Tests for Query message type."""

    def test_query_creation(self) -> None:
        """Test creating a Query."""
        # Query inherits from Message, which has 'message_type' not 'query_type'
        query = Query()

        assert query is not None
        assert query.include_deleted is False

    def test_query_with_options(self) -> None:
        """Test Query with caching options."""
        query = Query(
            include_deleted=True,
            cache_key="user-query-123",
            skip_cache=True,
        )

        assert query.include_deleted is True
        assert query.cache_key == "user-query-123"
        assert query.skip_cache is True


class TestPaginatedQuery:
    """Tests for PaginatedQuery."""

    def test_paginated_query_creation(self) -> None:
        """Test creating a PaginatedQuery."""
        query = PaginatedQuery(
            page=2,
            page_size=20,
        )

        assert query.page == 2
        assert query.page_size == 20

    def test_paginated_query_offset(self) -> None:
        """Test offset calculation."""
        query = PaginatedQuery(
            page=3,
            page_size=10,
        )

        assert query.offset == 20

    def test_paginated_query_limit(self) -> None:
        """Test limit calculation."""
        query = PaginatedQuery(
            page=1,
            page_size=25,
        )

        assert query.limit == 25


class TestPagedResult:
    """Tests for PagedResult."""

    def test_paged_result_creation(self) -> None:
        """Test creating a PagedResult."""
        result = PagedResult(
            items=[{"id": "1"}, {"id": "2"}],
            total=100,
            page=1,
            page_size=10,
        )

        assert len(result.items) == 2
        assert result.total == 100

    def test_paged_result_total_pages(self) -> None:
        """Test total pages calculation."""
        result = PagedResult(
            items=[],
            total=95,
            page=1,
            page_size=10,
        )

        assert result.total_pages == 10

    def test_paged_result_has_next(self) -> None:
        """Test has_next property."""
        result = PagedResult(
            items=[],
            total=100,
            page=5,
            page_size=20,
        )

        assert result.has_next is False

        result_current = PagedResult(
            items=[],
            total=100,
            page=4,
            page_size=20,
        )

        assert result_current.has_next is True

    def test_paged_result_has_prev(self) -> None:
        """Test has_prev property."""
        result = PagedResult(
            items=[],
            total=100,
            page=1,
            page_size=20,
        )

        assert result.has_prev is False

        result_multi = PagedResult(
            items=[],
            total=100,
            page=3,
            page_size=20,
        )

        assert result_multi.has_prev is True

    def test_paged_result_to_dict(self) -> None:
        """Test to_dict method."""
        result = PagedResult(
            items=[{"id": "1"}],
            total=50,
            page=2,
            page_size=10,
        )

        result_dict = result.to_dict()

        assert "items" in result_dict
        assert "total" in result_dict
        assert "page" in result_dict
        assert result_dict["total_pages"] == 5
