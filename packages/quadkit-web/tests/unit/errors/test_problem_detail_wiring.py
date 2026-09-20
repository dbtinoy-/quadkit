"""TDD tests for RFC 7807 Problem Details wiring.

These tests assert the new default error-response format:
- ``Content-Type: application/problem+json``
- Body containing the four mandatory RFC 7807 members:
  ``type``, ``title``, ``status``, ``detail``

All tests in this module FAIL before the implementation is applied and PASS
after ``error_to_response``, ``ValidationErrorFilter``,
``DependencyResolutionFilter``, and ``DefaultExceptionFilter`` are updated.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.web.exceptions import DependencyResolutionError, HTTPError
from quadkit.web.filters.builtin import (
    DefaultExceptionFilter,
    DependencyResolutionFilter,
    ValidationErrorFilter,
)
from quadkit.web.routing.result_bridge import ResultResponseMapper

_PROBLEM_JSON = "application/problem+json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(response) -> dict:
    """Decode the response body as JSON."""
    return json.loads(response.body)


def _content_type(response) -> str:
    """Return the Content-Type header value (lowercased, without params)."""
    raw = response.headers.get("content-type", "")
    return raw.split(";")[0].strip().lower()


# ---------------------------------------------------------------------------
# ResultResponseMapper.error_to_response
# ---------------------------------------------------------------------------


class TestErrorToResponseRFC7807:
    """``error_to_response`` must produce RFC 7807 Problem Details responses."""

    def test_content_type_is_problem_json_for_not_found_error(self) -> None:
        """Content-Type must be application/problem+json for NotFoundError."""
        error = NotFoundError("Widget not found")

        response = ResultResponseMapper.error_to_response(error)

        assert _content_type(response) == _PROBLEM_JSON

    def test_content_type_is_problem_json_for_validation_error(self) -> None:
        """Content-Type must be application/problem+json for ValidationError."""
        error = ValidationError("Bad input")

        response = ResultResponseMapper.error_to_response(error)

        assert _content_type(response) == _PROBLEM_JSON

    def test_content_type_is_problem_json_for_generic_error(self) -> None:
        """Content-Type must be application/problem+json for plain exceptions."""
        error = ValueError("oops")

        response = ResultResponseMapper.error_to_response(error)

        assert _content_type(response) == _PROBLEM_JSON

    def test_body_has_rfc7807_type_key(self) -> None:
        """RFC 7807 body must contain a ``type`` member."""
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))

        body = _parse(response)
        assert "type" in body

    def test_body_has_rfc7807_title_key(self) -> None:
        """RFC 7807 body must contain a ``title`` member."""
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))

        body = _parse(response)
        assert "title" in body

    def test_body_has_rfc7807_status_key(self) -> None:
        """RFC 7807 body must contain a ``status`` member."""
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))

        body = _parse(response)
        assert "status" in body

    def test_body_has_rfc7807_detail_key(self) -> None:
        """RFC 7807 body must contain a ``detail`` member."""
        response = ResultResponseMapper.error_to_response(NotFoundError("Widget 42"))

        body = _parse(response)
        assert "detail" in body

    def test_body_status_matches_http_status_code(self) -> None:
        """The RFC 7807 ``status`` value must equal the HTTP response status."""
        error = NotFoundError("user missing")

        response = ResultResponseMapper.error_to_response(error)

        body = _parse(response)
        assert body["status"] == 404
        assert response.status_code == 404

    def test_body_detail_contains_error_message_for_4xx(self) -> None:
        """The ``detail`` field must expose the error message for 4xx errors."""
        error = NotFoundError("Order 99 not found")

        response = ResultResponseMapper.error_to_response(error)

        body = _parse(response)
        assert "Order 99 not found" in body["detail"]

    def test_validation_error_body_status_is_422(self) -> None:
        """ValidationError must produce a 422 status in both header and body."""
        error = ValidationError("bad value")

        response = ResultResponseMapper.error_to_response(error)

        body = _parse(response)
        assert response.status_code == 422
        assert body["status"] == 422


# ---------------------------------------------------------------------------
# ValidationErrorFilter
# ---------------------------------------------------------------------------


class TestValidationErrorFilterRFC7807:
    """``ValidationErrorFilter`` must produce RFC 7807 responses with status 422."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Minimal mock request."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_content_type_is_problem_json(self, mock_request) -> None:
        """Content-Type must be application/problem+json."""
        exc = ValidationError("Invalid payload")
        flt = ValidationErrorFilter()

        response = await flt.handle(exc, mock_request)

        assert _content_type(response) == _PROBLEM_JSON

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_type_key(self, mock_request) -> None:
        """RFC 7807 body must contain a ``type`` member."""
        flt = ValidationErrorFilter()

        response = await flt.handle(ValidationError("bad"), mock_request)

        body = _parse(response)
        assert "type" in body

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_title_key(self, mock_request) -> None:
        """RFC 7807 body must contain a ``title`` member."""
        flt = ValidationErrorFilter()

        response = await flt.handle(ValidationError("bad"), mock_request)

        body = _parse(response)
        assert "title" in body

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_status_key(self, mock_request) -> None:
        """RFC 7807 body must contain a ``status`` member equal to 422."""
        flt = ValidationErrorFilter()

        response = await flt.handle(ValidationError("bad"), mock_request)

        body = _parse(response)
        assert "status" in body
        assert body["status"] == 422

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_detail_key(self, mock_request) -> None:
        """RFC 7807 body must contain a ``detail`` member."""
        flt = ValidationErrorFilter()

        response = await flt.handle(ValidationError("bad"), mock_request)

        body = _parse(response)
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_body_has_errors_list(self, mock_request) -> None:
        """RFC 7807 body must contain an ``errors`` extension list when present."""
        exc = ValidationError("bad payload")
        exc.add_error("email", "must be valid", "invalid_email")
        flt = ValidationErrorFilter()

        response = await flt.handle(exc, mock_request)

        body = _parse(response)
        assert "errors" in body
        assert isinstance(body["errors"], list)

    @pytest.mark.asyncio
    async def test_http_status_is_422(self, mock_request) -> None:
        """HTTP status code must be 422."""
        flt = ValidationErrorFilter()

        response = await flt.handle(ValidationError("bad"), mock_request)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DependencyResolutionFilter
# ---------------------------------------------------------------------------


class TestDependencyResolutionFilterRFC7807:
    """``DependencyResolutionFilter`` must produce RFC 7807 responses."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Minimal mock request."""
        return MagicMock()

    @pytest.fixture
    def dep_exc(self) -> DependencyResolutionError:
        """A typical DependencyResolutionError."""

        class _FakeService:
            pass

        return DependencyResolutionError(param="repo", service_type=_FakeService)

    @pytest.mark.asyncio
    async def test_content_type_is_problem_json(self, dep_exc, mock_request) -> None:
        """Content-Type must be application/problem+json."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        assert _content_type(response) == _PROBLEM_JSON

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_type_key(self, dep_exc, mock_request) -> None:
        """RFC 7807 body must contain a ``type`` member."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        body = _parse(response)
        assert "type" in body

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_title_key(self, dep_exc, mock_request) -> None:
        """RFC 7807 body must contain a ``title`` member."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        body = _parse(response)
        assert "title" in body

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_status_key(self, dep_exc, mock_request) -> None:
        """RFC 7807 body must contain a ``status`` member equal to 500."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        body = _parse(response)
        assert "status" in body
        assert body["status"] == 500

    @pytest.mark.asyncio
    async def test_body_has_rfc7807_detail_key(self, dep_exc, mock_request) -> None:
        """RFC 7807 body must contain a ``detail`` member."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        body = _parse(response)
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_http_status_is_500(self, dep_exc, mock_request) -> None:
        """HTTP status code must be 500."""
        flt = DependencyResolutionFilter()

        response = await flt.handle(dep_exc, mock_request)

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# DefaultExceptionFilter
# ---------------------------------------------------------------------------


class TestDefaultExceptionFilterRFC7807:
    """``DefaultExceptionFilter`` must produce RFC 7807 responses."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Minimal mock request."""
        req = MagicMock()
        req.url = "http://localhost/test"
        return req

    @pytest.fixture
    def default_filter(self) -> DefaultExceptionFilter:
        """Non-debug filter instance."""
        return DefaultExceptionFilter(debug=False)

    # --- HTTPError -----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_http_error_content_type_is_problem_json(
        self, default_filter, mock_request
    ) -> None:
        """Content-Type must be application/problem+json for HTTPError."""
        exc = HTTPError(status_code=404, detail="Not Found", code="NOT_FOUND")

        response = await default_filter.handle(exc, mock_request)

        assert _content_type(response) == _PROBLEM_JSON

    @pytest.mark.asyncio
    async def test_http_error_body_has_rfc7807_keys(
        self, default_filter, mock_request
    ) -> None:
        """HTTPError response body must contain all four RFC 7807 mandatory keys."""
        exc = HTTPError(status_code=409, detail="Already exists", code="CONFLICT")

        response = await default_filter.handle(exc, mock_request)

        body = _parse(response)
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_http_error_body_status_matches_status_code(
        self, default_filter, mock_request
    ) -> None:
        """The RFC 7807 ``status`` field must match the HTTP status code."""
        exc = HTTPError(status_code=403, detail="Forbidden", code="FORBIDDEN")

        response = await default_filter.handle(exc, mock_request)

        body = _parse(response)
        assert body["status"] == 403
        assert response.status_code == 403

    # --- Domain errors -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_domain_not_found_content_type_is_problem_json(
        self, default_filter, mock_request
    ) -> None:
        """Content-Type must be application/problem+json for domain NotFoundError."""
        exc = NotFoundError("Item missing")

        response = await default_filter.handle(exc, mock_request)

        assert _content_type(response) == _PROBLEM_JSON

    @pytest.mark.asyncio
    async def test_domain_error_body_has_rfc7807_keys(
        self, default_filter, mock_request
    ) -> None:
        """Domain error response body must contain all four RFC 7807 mandatory keys."""
        exc = NotFoundError("Order 77")

        response = await default_filter.handle(exc, mock_request)

        body = _parse(response)
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_domain_not_found_body_status_is_404(
        self, default_filter, mock_request
    ) -> None:
        """RFC 7807 ``status`` must be 404 for NotFoundError."""
        exc = NotFoundError("missing resource")

        response = await default_filter.handle(exc, mock_request)

        body = _parse(response)
        assert body["status"] == 404
