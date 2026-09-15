"""Tests for domain protocols in quadkit-contracts."""


import pytest
from quadkit.contracts.domain.aggregates import AggregateRootProtocol
from quadkit.contracts.domain.pagination import (
    OffsetPageProtocol,
    CursorPageProtocol,
    CursorPage,
)


class TestAggregateRootProtocol:
    """Tests for AggregateRootProtocol."""

    def test_aggregate_root_protocol_is_protocol(self) -> None:
        """Test AggregateRootProtocol is a Protocol."""
        assert hasattr(AggregateRootProtocol, "__protocol_attrs__") or hasattr(AggregateRootProtocol, "__annotations__")

    def test_aggregate_root_has_add_event_method(self) -> None:
        """Test protocol has add_event method."""
        assert hasattr(AggregateRootProtocol, "add_event")

    def test_aggregate_root_has_collect_events_method(self) -> None:
        """Test protocol has collect_events method."""
        assert hasattr(AggregateRootProtocol, "collect_events")

    def test_aggregate_root_has_pull_events_method(self) -> None:
        """Test protocol has pull_events method."""
        assert hasattr(AggregateRootProtocol, "pull_events")

    def test_aggregate_root_has_clear_events_method(self) -> None:
        """Test protocol has clear_events method."""
        assert hasattr(AggregateRootProtocol, "clear_events")

    def test_aggregate_root_has_uncommitted_events_property(self) -> None:
        """Test protocol has has_uncommitted_events property."""
        assert hasattr(AggregateRootProtocol, "has_uncommitted_events")


class TestOffsetPageProtocol:
    """Tests for OffsetPageProtocol."""

    def test_offset_page_is_protocol(self) -> None:
        """Test OffsetPageProtocol is a Protocol."""
        assert hasattr(OffsetPageProtocol, "__protocol_attrs__") or hasattr(OffsetPageProtocol, "__annotations__")

    def test_has_offset_property(self) -> None:
        """Test protocol has offset property."""
        assert hasattr(OffsetPageProtocol, "offset")

    def test_has_limit_property(self) -> None:
        """Test protocol has limit property."""
        assert hasattr(OffsetPageProtocol, "limit")


class TestCursorPageProtocol:
    """Tests for CursorPageProtocol."""

    def test_cursor_page_is_protocol(self) -> None:
        """Test CursorPageProtocol is a Protocol."""
        assert hasattr(CursorPageProtocol, "__protocol_attrs__") or hasattr(CursorPageProtocol, "__annotations__")

    def test_has_items_property(self) -> None:
        """Test protocol has items property."""
        assert hasattr(CursorPageProtocol, "items")

    def test_has_next_cursor_property(self) -> None:
        """Test protocol has next_cursor property."""
        assert hasattr(CursorPageProtocol, "next_cursor")

    def test_has_has_more_property(self) -> None:
        """Test protocol has has_more property."""
        assert hasattr(CursorPageProtocol, "has_more")


class TestCursorPage:
    """Tests for CursorPage concrete class."""

    def test_cursor_page_creation(self) -> None:
        """Test creating a CursorPage."""
        page = CursorPage(items=[1, 2, 3], next_cursor="abc", has_more=True)
        assert len(page.items) == 3
        assert page.next_cursor == "abc"
        assert page.has_more is True

    def test_cursor_page_empty(self) -> None:
        """Test creating empty CursorPage."""
        page = CursorPage(items=[], next_cursor=None, has_more=False)
        assert len(page.items) == 0
        assert page.next_cursor is None
        assert page.has_more is False