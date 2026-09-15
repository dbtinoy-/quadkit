"""Tests verifying RFC 7807 Problem Details format across all error paths."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from quadkit.result import Err
from quadkit.web.exceptions import HTTPError
from quadkit.web.filters.builtin import (
    DefaultExceptionFilter,
    DependencyResolutionFilter,
    ValidationErrorFilter,
)
from quadkit.web.routing.result_bridge import ResultResponseMapper


PROBLEM_JSON = "application/problem+json"
RFC7807_REQUIRED_KEYS = {"type", "title", "status", "detail"}


def _decode(response) -> dict:
    return json.loads(response.body.decode())


# ---------------------------------------------------------------------------
# ResultResponseMapper.error_to_response
# ---------------------------------------------------------------------------


class TestResultBridgeRFC7807:
    """error_to_response must emit RFC 7807 bodies with correct Content-Type."""

    def test_content_type_is_problem_json(self) -> None:
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))
        ct = dict(response.headers).get("content-type", "")
        assert PROBLEM_JSON in ct

    def test_body_has_all_required_fields(self) -> None:
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))
        body = _decode(response)
        assert RFC7807_REQUIRED_KEYS <= body.keys()

    def test_status_field_matches_http_status(self) -> None:
        response = ResultResponseMapper.error_to_response(NotFoundError("not found"))
        body = _decode(response)
        assert body["status"] == 404
        assert response.status_code == 404

    def test_detail_contains_exception_message(self) -> None:
        response = ResultResponseMapper.error_to_response(NotFoundError("User 42 not found"))
        body = _decode(response)
        assert "User 42 not found" in body["detail"]

    def test_result_err_produces_rfc7807(self) -> None:
        mapper = ResultResponseMapper()
        response = mapper.to_response(Err(ConflictError("already exists")))
        body = _decode(response)
        assert body["status"] == 409
        assert RFC7807_REQUIRED_KEYS <= body.keys()


# ---------------------------------------------------------------------------
# ValidationErrorFilter
# ---------------------------------------------------------------------------


class TestValidationErrorFilterRFC7807:
    """ValidationErrorFilter must emit RFC 7807 422 with errors list."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        return MagicMock()

    @pytest.mark.asyncio
    async def test_content_type_is_problem_json(self, mock_request) -> None:
        f = ValidationErrorFilter()
        exc = ValidationError("bad input")
        resp = await f.handle(exc, mock_request)
        ct = dict(resp.headers).get("content-type", "")
        assert PROBLEM_JSON in ct

    @pytest.mark.asyncio
    async def test_status_422(self, mock_request) -> None:
        f = ValidationErrorFilter()
        exc = ValidationError("bad input")
        resp = await f.handle(exc, mock_request)
        assert resp.status_code == 422
        assert _decode(resp)["status"] == 422

    @pytest.mark.asyncio
    async def test_body_has_required_fields(self, mock_request) -> None:
        f = ValidationErrorFilter()
        exc = ValidationError("bad input")
        resp = await f.handle(exc, mock_request)
        body = _decode(resp)
        assert RFC7807_REQUIRED_KEYS <= body.keys()

    @pytest.mark.asyncio
    async def test_type_is_validation_error_urn(self, mock_request) -> None:
        f = ValidationErrorFilter()
        exc = ValidationError("bad input")
        resp = await f.handle(exc, mock_request)
        assert _decode(resp)["type"] == "urn:quadkit:validation-error"

    @pytest.mark.asyncio
    async def test_errors_list_present(self, mock_request) -> None:
        f = ValidationErrorFilter()
        exc = ValidationError("field required")
        exc.add_error("name", "field required", "missing")
        resp = await f.handle(exc, mock_request)
        body = _decode(resp)
        assert isinstance(body.get("errors"), list)


# ---------------------------------------------------------------------------
# DependencyResolutionFilter
# ---------------------------------------------------------------------------


class TestDependencyResolutionFilterRFC7807:
    """DependencyResolutionFilter must emit RFC 7807 500."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        return MagicMock()

    @pytest.mark.asyncio
    async def test_content_type_is_problem_json(self, mock_request) -> None:
        from quadkit.web.exceptions import DependencyResolutionError

        f = DependencyResolutionFilter()
        exc = DependencyResolutionError("svc_param", str)
        resp = await f.handle(exc, mock_request)
        ct = dict(resp.headers).get("content-type", "")
        assert PROBLEM_JSON in ct

    @pytest.mark.asyncio
    async def test_status_500(self, mock_request) -> None:
        from quadkit.web.exceptions import DependencyResolutionError

        f = DependencyResolutionFilter()
        exc = DependencyResolutionError("svc_param", str)
        resp = await f.handle(exc, mock_request)
        assert resp.status_code == 500
        assert _decode(resp)["status"] == 500

    @pytest.mark.asyncio
    async def test_body_has_required_fields(self, mock_request) -> None:
        from quadkit.web.exceptions import DependencyResolutionError

        f = DependencyResolutionFilter()
        exc = DependencyResolutionError("svc_param", str)
        resp = await f.handle(exc, mock_request)
        assert RFC7807_REQUIRED_KEYS <= _decode(resp).keys()


# ---------------------------------------------------------------------------
# DefaultExceptionFilter — domain errors
# ---------------------------------------------------------------------------


class TestDefaultExceptionFilterRFC7807:
    """DefaultExceptionFilter must emit RFC 7807 for all error types."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        req = MagicMock()
        req.url = "http://localhost/test"
        return req

    @pytest.mark.asyncio
    async def test_not_found_content_type(self, mock_request) -> None:
        f = DefaultExceptionFilter()
        resp = await f.handle(NotFoundError("gone"), mock_request)
        ct = dict(resp.headers).get("content-type", "")
        assert PROBLEM_JSON in ct

    @pytest.mark.asyncio
    async def test_not_found_rfc7807_type_uri(self, mock_request) -> None:
        f = DefaultExceptionFilter()
        resp = await f.handle(NotFoundError("gone"), mock_request)
        assert _decode(resp)["type"] == "urn:quadkit:not-found"

    @pytest.mark.asyncio
    async def test_permission_denied_is_403_forbidden(self, mock_request) -> None:
        f = DefaultExceptionFilter()
        resp = await f.handle(PermissionDeniedError("no access"), mock_request)
        assert resp.status_code == 403
        assert _decode(resp)["type"] == "urn:quadkit:forbidden"

    @pytest.mark.asyncio
    async def test_http_error_content_type(self, mock_request) -> None:
        f = DefaultExceptionFilter()
        exc = HTTPError(status_code=418, detail="I'm a teapot", code="TEAPOT")
        resp = await f.handle(exc, mock_request)
        ct = dict(resp.headers).get("content-type", "")
        assert PROBLEM_JSON in ct

    @pytest.mark.asyncio
    async def test_http_error_rfc7807_body(self, mock_request) -> None:
        f = DefaultExceptionFilter()
        exc = HTTPError(status_code=418, detail="I'm a teapot", code="TEAPOT")
        resp = await f.handle(exc, mock_request)
        body = _decode(resp)
        assert resp.status_code == 418
        assert body["status"] == 418
        assert "teapot" in body["type"].lower()
        assert "I'm a teapot" in body["detail"]
        assert RFC7807_REQUIRED_KEYS <= body.keys()
