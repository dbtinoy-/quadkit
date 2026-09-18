"""Tests for contracts/web/types.py — HTTP response envelope types."""

from __future__ import annotations

import pytest

from quadkit.contracts.web.types import (
    ErrorDetail,
    ErrorResponseDTO,
    PaginatedResponseDTO,
)


class TestErrorDetail:
    """Tests for ErrorDetail dataclass."""

    def test_error_detail_creation(self) -> None:
        """ErrorDetail creates with required fields."""
        detail = ErrorDetail(code="INVALID_INPUT", message="Invalid value")
        assert detail.code == "INVALID_INPUT"
        assert detail.message == "Invalid value"

    def test_error_detail_with_field(self) -> None:
        """ErrorDetail accepts optional field."""
        detail = ErrorDetail(code="INVALID_FIELD", message="Invalid", field="email")
        assert detail.field == "email"

    def test_error_detail_field_default_none(self) -> None:
        """ErrorDetail defaults field to None."""
        detail = ErrorDetail(code="X", message="Y")
        assert detail.field is None

    def test_error_detail_is_frozen(self) -> None:
        """ErrorDetail is frozen."""
        detail = ErrorDetail(code="X", message="Y")
        with pytest.raises(AttributeError):
            detail.code = "Z"


class TestErrorResponseDTO:
    """Tests for ErrorResponseDTO dataclass."""

    def test_error_response_creation(self) -> None:
        """ErrorResponseDTO creates with required fields."""
        response = ErrorResponseDTO(
            error="BadRequest",
            message="Invalid request",
        )
        assert response.error == "BadRequest"
        assert response.message == "Invalid request"

    def test_error_response_with_details(self) -> None:
        """ErrorResponseDTO accepts error details."""
        detail = ErrorDetail(code="INVALID", message="Bad value", field="age")
        response = ErrorResponseDTO(
            error="ValidationError",
            message="Validation failed",
            details=[detail],
        )
        assert len(response.details) == 1
        assert response.details[0].field == "age"

    def test_error_response_default_details(self) -> None:
        """ErrorResponseDTO defaults details to empty list."""
        response = ErrorResponseDTO(error="X", message="Y")
        assert response.details == []

    def test_error_response_with_request_id(self) -> None:
        """ErrorResponseDTO accepts request_id."""
        response = ErrorResponseDTO(
            error="InternalError",
            message="Something went wrong",
            request_id="req-123",
        )
        assert response.request_id == "req-123"

    def test_error_response_request_id_default_none(self) -> None:
        """ErrorResponseDTO defaults request_id to None."""
        response = ErrorResponseDTO(error="X", message="Y")
        assert response.request_id is None

    def test_error_response_is_frozen(self) -> None:
        """ErrorResponseDTO is frozen."""
        response = ErrorResponseDTO(error="X", message="Y")
        with pytest.raises(AttributeError):
            response.error = "Z"


class TestPaginatedResponseDTO:
    """Tests for PaginatedResponseDTO generic dataclass."""

    def test_paginated_response_creation(self) -> None:
        """PaginatedResponseDTO creates with required fields."""
        response = PaginatedResponseDTO(
            items=[1, 2, 3],
            total=100,
            page=1,
            page_size=10,
            has_next=True,
            has_prev=False,
        )
        assert response.items == [1, 2, 3]
        assert response.total == 100

    def test_paginated_response_with_cursor(self) -> None:
        """PaginatedResponseDTO accepts cursor for next page."""
        response = PaginatedResponseDTO(
            items=["a", "b"],
            total=50,
            page=2,
            page_size=10,
            has_next=True,
            has_prev=True,
            next_cursor="cursor-abc",
        )
        assert response.next_cursor == "cursor-abc"

    def test_paginated_response_cursor_default_none(self) -> None:
        """PaginatedResponseDTO defaults cursor to None."""
        response = PaginatedResponseDTO(
            items=[],
            total=0,
            page=1,
            page_size=10,
            has_next=False,
            has_prev=False,
        )
        assert response.next_cursor is None

    def test_paginated_response_first_page(self) -> None:
        """PaginatedResponseDTO first page has_prev is False."""
        response = PaginatedResponseDTO(
            items=[1, 2],
            total=50,
            page=1,
            page_size=10,
            has_next=True,
            has_prev=False,
        )
        assert response.has_prev is False

    def test_paginated_response_last_page(self) -> None:
        """PaginatedResponseDTO last page has_next is False."""
        response = PaginatedResponseDTO(
            items=[1, 2],
            total=20,
            page=2,
            page_size=10,
            has_next=False,
            has_prev=True,
        )
        assert response.has_next is False

    def test_paginated_response_is_frozen(self) -> None:
        """PaginatedResponseDTO is frozen."""
        response = PaginatedResponseDTO(
            items=[],
            total=0,
            page=1,
            page_size=10,
            has_next=False,
            has_prev=False,
        )
        with pytest.raises(AttributeError):
            response.total = 100

    def test_paginated_response_with_strings(self) -> None:
        """PaginatedResponseDTO works with string items."""
        response = PaginatedResponseDTO(
            items=["apple", "banana"],
            total=2,
            page=1,
            page_size=10,
            has_next=False,
            has_prev=False,
        )
        assert response.items == ["apple", "banana"]

    def test_paginated_response_with_dicts(self) -> None:
        """PaginatedResponseDTO works with dict items."""
        response = PaginatedResponseDTO(
            items=[{"id": 1}, {"id": 2}],
            total=5,
            page=1,
            page_size=2,
            has_next=True,
            has_prev=False,
        )
        assert len(response.items) == 2
        assert response.items[0]["id"] == 1
