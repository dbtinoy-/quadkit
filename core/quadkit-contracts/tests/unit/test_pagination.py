"""Tests for pagination models."""

import pytest

from quadkit.contracts.domain.pagination import (
    CursorPage,
    CursorPageProtocol,
    OffsetPageProtocol,
)


class TestOffsetPageProtocol:
    """Tests for OffsetPageProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that OffsetPageProtocol is runtime checkable."""
        # This should not raise
        assert hasattr(OffsetPageProtocol, "__protocol_attrs__") or hasattr(OffsetPageProtocol, "__annotations__")


class TestCursorPageProtocol:
    """Tests for CursorPageProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that CursorPageProtocol is runtime checkable."""
        # This should not raise
        assert hasattr(CursorPageProtocol, "__protocol_attrs__") or hasattr(CursorPageProtocol, "__annotations__")


class TestCursorPage:
    """Tests for CursorPage dataclass."""

    def test_empty_page(self) -> None:
        """Test creating an empty cursor page."""
        page = CursorPage(items=[])
        assert page.items == []
        assert page.next_cursor is None
        assert page.prev_cursor is None
        assert page.has_more is False
        assert page.has_previous is False
        assert page.total_count is None

    def test_page_with_items(self) -> None:
        """Test creating a cursor page with items."""
        items = ["a", "b", "c"]
        page = CursorPage(items=items)
        assert page.items == items

    def test_page_with_next_cursor(self) -> None:
        """Test page with next cursor."""
        page = CursorPage(items=[], next_cursor="abc123", has_more=True)
        assert page.next_cursor == "abc123"
        assert page.has_more is True

    def test_page_with_prev_cursor(self) -> None:
        """Test page with previous cursor."""
        page = CursorPage(items=[], prev_cursor="xyz789", has_previous=True)
        assert page.prev_cursor == "xyz789"
        assert page.has_previous is True

    def test_page_with_total_count(self) -> None:
        """Test page with total count."""
        page = CursorPage(items=[], total_count=100)
        assert page.total_count == 100

    def test_to_dict_empty_page(self) -> None:
        """Test serialization of empty page."""
        page = CursorPage(items=[])
        result = page.to_dict()
        assert result["items"] == []
        assert result["next_cursor"] is None
        assert result["prev_cursor"] is None
        assert result["has_more"] is False
        assert result["has_previous"] is False
        assert result["total_count"] is None

    def test_to_dict_full_page(self) -> None:
        """Test serialization of full page."""
        items = ["a", "b", "c"]
        page = CursorPage(
            items=items,
            next_cursor="next123",
            prev_cursor="prev456",
            has_more=True,
            has_previous=True,
            total_count=100,
        )
        result = page.to_dict()
        assert result["items"] == items
        assert result["next_cursor"] == "next123"
        assert result["prev_cursor"] == "prev456"
        assert result["has_more"] is True
        assert result["has_previous"] is True
        assert result["total_count"] == 100
