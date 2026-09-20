"""Unit tests for the request ID contract.

One middleware assigns the request ID (``RequestContextMiddleware``); the
readers live in ``quadkit.web.middleware.request_id``. The last test here
pins the observable contract of the default stack: exactly one
``x-request-id`` response header whose value is the id the handler saw.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from quadkit.app.base import Application
from quadkit.web import Controller, get
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.middleware.request_context import RequestContextMiddleware
from quadkit.web.middleware.request_id import (
    RequestIDLogFilter,
    get_request_id_from_request,
)


class _EchoController(Controller):
    """Report the request id the handler observes."""

    @get("/echo-id")
    async def echo_id(self, request: Any) -> dict:
        return {"request_id": get_request_id_from_request(request)}


async def _default_stack_client() -> Any:
    """Boot a default web app and return a client over the mounted stack."""
    from starlette.testclient import TestClient

    app = Application(name="request-id-probe")
    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        controllers=[_EchoController],
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None
    return TestClient(web.starlette)


def test_request_id_surface_has_one_middleware() -> None:
    """The middleware package exports one request-id middleware, not two."""
    from quadkit.web import middleware

    assert "RequestContextMiddleware" in middleware.__all__
    assert middleware.RequestContextMiddleware is RequestContextMiddleware
    assert not hasattr(middleware, "RequestIDMiddleware")


@pytest.mark.asyncio
async def test_default_stack_writes_exactly_one_request_id_header() -> None:
    """A response carries one ``x-request-id`` and the handler saw that value."""
    client = await _default_stack_client()

    with client:
        response = client.get("/echo-id")
        missing = client.get("/definitely-not-a-route")

    response.raise_for_status()
    assert len(response.headers.get_list("x-request-id")) == 1
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert response.json()["request_id"].startswith("req_")
    # The same single-header contract holds for an error response.
    assert missing.status_code == 404
    assert len(missing.headers.get_list("x-request-id")) == 1


class TestRequestIDLogFilter:
    """Test request ID log filter."""

    @pytest.fixture
    def ctx(self):
        """Create a default context instance."""
        from quadkit.primitives.context import create_default_context

        return create_default_context()

    @pytest.fixture
    def log_filter(self, ctx) -> RequestIDLogFilter:
        """Create log filter instance with injected context."""
        return RequestIDLogFilter(ctx=ctx)

    def test_filter_adds_request_id_when_present(
        self,
        log_filter: RequestIDLogFilter,
        ctx,
    ) -> None:
        """Test that filter adds request ID to log record when present."""
        # Arrange
        from quadkit.primitives.context import REQUEST_ID

        token = ctx.set(REQUEST_ID, "test_request_id")
        try:
            record = Mock()
            record.request_id = None

            # Act
            result = log_filter.filter(record)

            # Assert
            assert result is True  # Should not filter out
            assert record.request_id == "test_request_id"
        finally:
            ctx.registry.resolve_var(REQUEST_ID).reset(token)

    def test_filter_adds_no_request_when_missing(
        self,
        log_filter: RequestIDLogFilter,
    ) -> None:
        """Test that filter adds 'no_request' when no request ID."""
        # Arrange — no REQUEST_ID set in ctx
        record = Mock()
        record.request_id = None

        # Act
        result = log_filter.filter(record)

        # Assert
        assert result is True
        assert record.request_id == "no_request"


class TestRequestIDUtilities:
    """Test request ID utility functions."""

    def test_get_request_id_from_request_with_id(self) -> None:
        """Test getting request ID from request state."""
        # Arrange
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test_id"

        # Act
        result = get_request_id_from_request(request)

        # Assert
        assert result == "test_id"

    def test_get_request_id_from_request_without_id(self) -> None:
        """Test getting request ID when not set."""
        # Arrange
        request = Mock(spec=Request)

        # Use a real object for state that doesn't have request_id
        class MockState:
            pass

        request.state = MockState()

        # Act
        result = get_request_id_from_request(request)

        # Assert
        assert result is None
