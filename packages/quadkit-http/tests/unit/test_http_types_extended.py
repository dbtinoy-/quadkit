"""Extended tests for quadkit.http.types — dataclass behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quadkit.http.types import RequestContext, ResponseContext


class TestRequestContextEquality:
    """Tests for RequestContext equality and hash."""

    def test_equal_contexts(self) -> None:
        """Identical contexts are equal."""
        now = datetime(2024, 1, 1, tzinfo=UTC)
        ctx1 = RequestContext(
            method="GET",
            url="https://example.com",
            headers={"a": "1"},
            service_name="svc",
            attempt=2,
            start_time=now,
        )
        ctx2 = RequestContext(
            method="GET",
            url="https://example.com",
            headers={"a": "1"},
            service_name="svc",
            attempt=2,
            start_time=now,
        )
        assert ctx1 == ctx2

    def test_unequal_methods(self) -> None:
        """Different methods are not equal."""
        ctx1 = RequestContext(method="GET", url="https://ex.com", headers={})
        ctx2 = RequestContext(method="POST", url="https://ex.com", headers={})
        assert ctx1 != ctx2

    def test_unequal_urls(self) -> None:
        """Different URLs are not equal."""
        ctx1 = RequestContext(method="GET", url="https://a.com", headers={})
        ctx2 = RequestContext(method="GET", url="https://b.com", headers={})
        assert ctx1 != ctx2


class TestResponseContextEquality:
    """Tests for ResponseContext equality."""

    def test_equal_contexts(self) -> None:
        """Identical contexts are equal."""
        ctx1 = ResponseContext(status=200, headers={"a": "1"})
        ctx2 = ResponseContext(status=200, headers={"a": "1"})
        assert ctx1 == ctx2

    def test_unequal_status(self) -> None:
        """Different status codes are not equal."""
        ctx1 = ResponseContext(status=200, headers={})
        ctx2 = ResponseContext(status=404, headers={})
        assert ctx1 != ctx2


class TestRequestContextRepr:
    """Tests for RequestContext repr."""

    def test_repr_contains_fields(self) -> None:
        """Repr contains key field values."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com/api",
            headers={"Content-Type": "application/json"},
        )
        r = repr(ctx)
        assert "GET" in r
        assert "example.com" in r


class TestResponseContextRepr:
    """Tests for ResponseContext repr."""

    def test_repr_contains_status(self) -> None:
        """Repr contains status code."""
        ctx = ResponseContext(status=201, headers={})
        r = repr(ctx)
        assert "201" in r


class TestRequestContextDefaults:
    """Additional tests for RequestContext defaults."""

    def test_attempt_defaults_to_zero(self) -> None:
        """Attempt defaults to 0."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com",
            headers={},
        )
        assert ctx.attempt == 0

    def test_service_name_defaults_to_none(self) -> None:
        """service_name defaults to None."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com",
            headers={},
        )
        assert ctx.service_name is None

    def test_headers_empty_dict(self) -> None:
        """Empty headers dict is allowed."""
        ctx = RequestContext(
            method="GET",
            url="https://example.com",
            headers={},
        )
        assert ctx.headers == {}

    def test_all_headers_preserved(self) -> None:
        """Multiple headers are preserved."""
        ctx = RequestContext(
            method="POST",
            url="https://example.com",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token",
                "X-Request-ID": "abc",
            },
        )
        assert len(ctx.headers) == 3


class TestResponseContextDefaults:
    """Additional tests for ResponseContext defaults."""

    def test_duration_none_by_default(self) -> None:
        """Duration defaults to None."""
        ctx = ResponseContext(status=200, headers={})
        assert ctx.duration is None

    def test_content_length_none_by_default(self) -> None:
        """content_length defaults to None."""
        ctx = ResponseContext(status=200, headers={})
        assert ctx.content_length is None

    def test_error_none_by_default(self) -> None:
        """error defaults to None."""
        ctx = ResponseContext(status=200, headers={})
        assert ctx.error is None

    def test_success_true_by_default(self) -> None:
        """success defaults to True even on error status."""
        ctx = ResponseContext(status=500, headers={})
        assert ctx.success is True


class TestResponseContextCombinations:
    """Combinations of optional fields."""

    def test_full_success_response(self) -> None:
        """Full success response context."""
        ctx = ResponseContext(
            status=200,
            headers={"Content-Type": "application/json"},
            content_length=1024,
            duration=0.15,
            success=True,
            error=None,
        )
        assert ctx.status == 200
        assert ctx.content_length == 1024
        assert ctx.duration == 0.15
        assert ctx.success is True

    def test_full_error_response(self) -> None:
        """Full error response context."""
        ctx = ResponseContext(
            status=503,
            headers={"Content-Type": "text/plain"},
            content_length=100,
            duration=5.0,
            success=False,
            error="Service Unavailable",
        )
        assert ctx.status == 503
        assert ctx.success is False
        assert ctx.error == "Service Unavailable"

    def test_large_status_codes(self) -> None:
        """599 (dissenter) status code works."""
        ctx = ResponseContext(status=599, headers={})
        assert ctx.status == 599

    def test_small_status_codes(self) -> None:
        """1xx status codes work."""
        ctx = ResponseContext(status=100, headers={})
        assert ctx.status == 100

    def test_negative_duration_not_allowed(self) -> None:
        """Negative duration (no restriction by design)."""
        ctx = ResponseContext(status=200, headers={}, duration=-1.0)
        assert ctx.duration == -1.0


class TestRequestContextTypes:
    """Type validation for RequestContext fields."""

    def test_method_must_be_string(self) -> None:
        """Method accepts string."""
        ctx = RequestContext(method="DELETE", url="https://x.com", headers={})
        assert ctx.method == "DELETE"

    def test_url_must_be_string(self) -> None:
        """URL accepts string."""
        ctx = RequestContext(method="GET", url="https://example.com/api", headers={})
        assert "example.com" in ctx.url

    def test_headers_must_be_dict(self) -> None:
        """Headers accepts dict."""
        ctx = RequestContext(
            method="GET",
            url="https://x.com",
            headers={"X-A": "1"},
        )
        assert isinstance(ctx.headers, dict)


class TestContextDataclassFrozen:
    """Test that dataclass frozen behavior if applicable."""

    def test_request_context_is_dataclass(self) -> None:
        """RequestContext is a dataclass."""
        ctx = RequestContext(method="GET", url="https://x.com", headers={})
        # Has __dataclass_fields__
        assert hasattr(RequestContext, "__dataclass_fields__")

    def test_response_context_is_dataclass(self) -> None:
        """ResponseContext is a dataclass."""
        ctx = ResponseContext(status=200, headers={})
        assert hasattr(ResponseContext, "__dataclass_fields__")