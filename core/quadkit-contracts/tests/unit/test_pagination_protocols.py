"""Tests for pagination protocols."""

from __future__ import annotations

from quadkit.contracts.domain.pagination import (
    OffsetPageProtocol,
    CursorPageProtocol,
    CursorPage,
)


class TestOffsetPageProtocol:
    """Tests for OffsetPageProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(OffsetPageProtocol, "__protocol_attrs__") or hasattr(OffsetPageProtocol, "__annotations__")

    def test_has_offset_property(self) -> None:
        assert hasattr(OffsetPageProtocol, "offset")

    def test_has_limit_property(self) -> None:
        assert hasattr(OffsetPageProtocol, "limit")


class TestCursorPageProtocol:
    """Tests for CursorPageProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(CursorPageProtocol, "__protocol_attrs__") or hasattr(CursorPageProtocol, "__annotations__")

    def test_has_items_property(self) -> None:
        assert hasattr(CursorPageProtocol, "items")

    def test_has_next_cursor_property(self) -> None:
        assert hasattr(CursorPageProtocol, "next_cursor")

    def test_has_has_more_property(self) -> None:
        assert hasattr(CursorPageProtocol, "has_more")


class TestCursorPage:
    """Tests for CursorPage dataclass."""

    def test_create_minimal(self) -> None:
        page = CursorPage(items=[1, 2, 3])
        assert page.items == [1, 2, 3]
        assert page.next_cursor is None
        assert page.has_more is False

    def test_create_full(self) -> None:
        page = CursorPage(
            items=["a", "b"],
            next_cursor="next123",
            prev_cursor="prev123",
            has_more=True,
            has_previous=True,
            total_count=100,
        )
        assert page.items == ["a", "b"]
        assert page.next_cursor == "next123"
        assert page.prev_cursor == "prev123"
        assert page.has_more is True
        assert page.has_previous is True
        assert page.total_count == 100

    def test_to_dict(self) -> None:
        page = CursorPage(items=[1, 2], has_more=True)
        d = page.to_dict()
        assert d["items"] == [1, 2]
        assert d["has_more"] is True
        assert "next_cursor" in d