"""Tests for DefaultExceptionFilter — handling domain and HTTP errors."""

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.exceptions.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from quadkit.web.filters.builtin import DefaultExceptionFilter


class TestDefaultExceptionFilterCanHandle:
    """Tests for DefaultExceptionFilter.can_handle."""

    def test_can_handle_domain_error(self) -> None:
        f = DefaultExceptionFilter()
        assert f.can_handle(DomainError("test"))

    def test_can_handle_not_found_error(self) -> None:
        f = DefaultExceptionFilter()
        assert f.can_handle(NotFoundError("not found"))

    def test_can_handle_authentication_error(self) -> None:
        f = DefaultExceptionFilter()
        # AuthenticationError is a DomainError
        assert f.can_handle(AuthenticationError("unauthenticated"))

    def test_does_not_handle_plain_exception(self) -> None:
        f = DefaultExceptionFilter()
        assert not f.can_handle(ValueError("not domain"))


class TestDefaultExceptionFilterHandle:
    """Tests for DefaultExceptionFilter.handle — status code mapping."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        req = MagicMock()
        req.url = "http://localhost/test"
        return req

    @pytest.fixture
    def default_filter(self) -> DefaultExceptionFilter:
        return DefaultExceptionFilter()

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, default_filter, mock_request) -> None:
        exc = NotFoundError("User not found")
        resp = await default_filter.handle(exc, mock_request)
        assert resp.status_code == 404
        import json
        body = json.loads(resp.body.decode())
        assert body.get("type") == "urn:quadkit:not-found"
        assert "User not found" in body.get("detail", "")

    @pytest.mark.asyncio
    async def test_permission_denied_returns_403(self, default_filter, mock_request) -> None:
        exc = PermissionDeniedError("Access denied")
        resp = await default_filter.handle(exc, mock_request)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_conflict_returns_409(self, default_filter, mock_request) -> None:
        exc = ConflictError("Already exists")
        resp = await default_filter.handle(exc, mock_request)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_generic_domain_error_returns_400(self, default_filter, mock_request) -> None:
        exc = DomainError("Something went wrong")
        resp = await default_filter.handle(exc, mock_request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_http_error_returns_its_status(self, default_filter, mock_request) -> None:
        from quadkit.web.exceptions import HTTPError
        exc = HTTPError(status_code=418, detail="I'm a teapot", code="TEAPOT")
        resp = await default_filter.handle(exc, mock_request)
        assert resp.status_code == 418
        import json
        body = json.loads(resp.body.decode())
        assert "teapot" in body.get("type", "").lower()
        assert "I'm a teapot" in body.get("detail", "")
