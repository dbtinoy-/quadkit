"""Unit tests for quadkit.http.types."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from quadkit.http.types import RequestContext, ResponseContext


class TestRequestContext:
    """Tests for RequestContext dataclass."""

    def test_required_fields(self) -> None:
        """Test that required fields are correctly set."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com/api",
            headers={"Content-Type": "application/json"},
        )
        assert ctx.method == "GET"
        assert ctx.url == "https://example.com/api"
        assert ctx.headers == {"Content-Type": "application/json"}

    def test_optional_fields_default_to_none(self) -> None:
        """Test optional fields have correct defaults."""
        ctx = RequestContext(
            method="POST",
            url="https://example.com/data",
            headers={},
        )
        assert ctx.service_name is None
        assert ctx.attempt == 0
        assert ctx.start_time is not None

    def test_optional_fields_accept_values(self) -> None:
        """Test optional fields accept custom values."""
        start = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        ctx = RequestContext(
            method="PUT",
            url="https://example.com/resource/1",
            headers={},
            service_name="users-api",
            attempt=3,
            start_time=start,
        )
        assert ctx.service_name == "users-api"
        assert ctx.attempt == 3
        assert ctx.start_time == start

    def test_start_time_auto_set_when_none(self) -> None:
        """Test start_time is auto-generated if not provided."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com",
            headers={},
        )
        now = datetime.now(UTC)
        assert ctx.start_time is not None
        assert ctx.start_time.year == now.year
        assert ctx.start_time.month == now.month


class TestResponseContext:
    """Tests for ResponseContext dataclass."""

    def test_required_fields(self) -> None:
        """Test that required fields are correctly set."""
        ctx = ResponseContext(
            status=200,
            headers={"Content-Type": "application/json"},
        )
        assert ctx.status == 200
        assert ctx.headers == {"Content-Type": "application/json"}

    def test_optional_fields_default_values(self) -> None:
        """Test optional fields have correct defaults."""
        ctx = ResponseContext(
            status=200,
            headers={},
        )
        assert ctx.content_length is None
        assert ctx.duration is None
        assert ctx.success is True
        assert ctx.error is None

    def test_success_flag_defaults_to_true(self) -> None:
        """Test success defaults to True."""
        ctx = ResponseContext(
            status=404,
            headers={},
        )
        assert ctx.success is True

    def test_success_flag_can_be_set_explicitly(self) -> None:
        """Test success can be set explicitly."""
        ctx = ResponseContext(
            status=404,
            headers={},
            success=False,
        )
        assert ctx.success is False

        ctx = ResponseContext(
            status=500,
            headers={},
            success=False,
        )
        assert ctx.success is False

    def test_error_field_with_failed_request(self) -> None:
        """Test error field is set for failed requests."""
        ctx = ResponseContext(
            status=403,
            headers={},
            error="Forbidden",
        )
        assert ctx.error == "Forbidden"

    def test_content_length_field(self) -> None:
        """Test content_length field."""
        ctx = ResponseContext(
            status=200,
            headers={},
            content_length=1024,
        )
        assert ctx.content_length == 1024

    def test_duration_field(self) -> None:
        """Test duration field."""
        ctx = ResponseContext(
            status=200,
            headers={},
            duration=0.25,
        )
        assert ctx.duration == 0.25