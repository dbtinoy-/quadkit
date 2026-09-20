"""Tests for pagination models."""
from __future__ import annotations

import pytest

from quadkit.web.pagination.models import Page, PageRequest, cursor_page_to_response, paginated
from quadkit.contracts.domain.pagination import CursorPage


class TestPageRequest:
    """Tests for PageRequest dataclass."""

    def test_defaults(self) -> None:
        req = PageRequest()
        assert req.page == 1
        assert req.size == 20
        assert req.sort_by is None
        assert req.sort_order == "asc"

    def test_offset_calculation(self) -> None:
        req = PageRequest(page=3, size=10)
        assert req.offset == 20

    def test_limit_equals_size(self) -> None:
        req = PageRequest(page=1, size=25)
        assert req.limit == 25

    def test_first_page_offset_is_zero(self) -> None:
        req = PageRequest(page=1, size=20)
        assert req.offset == 0

    def test_sort_fields(self) -> None:
        req = PageRequest(sort_by="created_at", sort_order="desc")
        assert req.sort_by == "created_at"
        assert req.sort_order == "desc"


class TestPage:
    """Tests for Page dataclass."""

    def test_pages_calculated(self) -> None:
        page = Page(items=[1, 2, 3], total=30, page=1, size=10)
        assert page.pages == 3

    def test_pages_ceil_division(self) -> None:
        page = Page(items=[], total=21, page=1, size=10)
        assert page.pages == 3

    def test_has_next(self) -> None:
        page = Page(items=[], total=30, page=1, size=10)
        assert page.has_next is True

    def test_no_next_on_last_page(self) -> None:
        page = Page(items=[], total=30, page=3, size=10)
        assert page.has_next is False

    def test_has_prev(self) -> None:
        page = Page(items=[], total=30, page=2, size=10)
        assert page.has_prev is True

    def test_no_prev_on_first_page(self) -> None:
        page = Page(items=[], total=30, page=1, size=10)
        assert page.has_prev is False

    def test_next_page_value(self) -> None:
        page = Page(items=[], total=30, page=2, size=10)
        assert page.next_page == 3

    def test_next_page_none_on_last(self) -> None:
        page = Page(items=[], total=30, page=3, size=10)
        assert page.next_page is None

    def test_prev_page_value(self) -> None:
        page = Page(items=[], total=30, page=3, size=10)
        assert page.prev_page == 2

    def test_prev_page_none_on_first(self) -> None:
        page = Page(items=[], total=30, page=1, size=10)
        assert page.prev_page is None

    def test_to_response_envelope(self) -> None:
        page = Page(items=["a", "b"], total=2, page=1, size=10)
        result = page.to_response()
        assert result["items"] == ["a", "b"]
        meta = result["meta"]
        assert meta["total"] == 2
        assert meta["page"] == 1
        assert meta["size"] == 10
        assert meta["pages"] == 1
        assert meta["has_next"] is False
        assert meta["has_prev"] is False
        assert meta["next_page"] is None
        assert meta["prev_page"] is None

    def test_pages_zero_when_size_zero(self) -> None:
        page = Page(items=[], total=10, page=1, size=0)
        assert page.pages == 0


class TestCursorPageToResponse:
    """Tests for cursor_page_to_response helper."""

    def test_envelope_format(self) -> None:
        cp = CursorPage(
            items=["x", "y"],
            next_cursor="tok_next",
            prev_cursor="tok_prev",
            has_more=True,
        )
        result = cursor_page_to_response(cp)
        assert result["items"] == ["x", "y"]
        assert result["meta"]["next_cursor"] == "tok_next"
        assert result["meta"]["prev_cursor"] == "tok_prev"
        assert result["meta"]["has_more"] is True

    def test_envelope_no_cursors(self) -> None:
        cp = CursorPage(items=[], next_cursor=None, prev_cursor=None, has_more=False)
        result = cursor_page_to_response(cp)
        assert result["meta"]["next_cursor"] is None
        assert result["meta"]["prev_cursor"] is None
        assert result["meta"]["has_more"] is False


class TestPaginatedDecorator:
    """Tests for the @paginated decorator factory."""

    def test_returns_page_request_from_params(self) -> None:
        @paginated()
        def my_list(query_params):
            ...

        req = my_list({"page": "2", "size": "5"})
        assert req.page == 2
        assert req.size == 5

    def test_defaults_when_params_missing(self) -> None:
        @paginated(default_page=1, default_size=20)
        def my_list(query_params):
            ...

        req = my_list({})
        assert req.page == 1
        assert req.size == 20

    def test_page_clamped_to_minimum_1(self) -> None:
        @paginated()
        def my_list(query_params):
            ...

        req = my_list({"page": "0"})
        assert req.page == 1

    def test_size_clamped_to_max(self) -> None:
        @paginated(max_size=50)
        def my_list(query_params):
            ...

        req = my_list({"size": "999"})
        assert req.size == 50

    def test_size_clamped_to_min_1(self) -> None:
        @paginated()
        def my_list(query_params):
            ...

        req = my_list({"size": "-5"})
        assert req.size == 1

    def test_invalid_page_falls_back_to_default(self) -> None:
        @paginated(default_page=3)
        def my_list(query_params):
            ...

        req = my_list({"page": "not_a_number"})
        assert req.page == 3

    def test_invalid_size_falls_back_to_default(self) -> None:
        @paginated(default_size=15)
        def my_list(query_params):
            ...

        req = my_list({"size": "abc"})
        assert req.size == 15

    def test_custom_param_names(self) -> None:
        @paginated(page_param="p", size_param="limit")
        def my_list(query_params):
            ...

        req = my_list({"p": "3", "limit": "7"})
        assert req.page == 3
        assert req.size == 7
