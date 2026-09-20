"""Tests for StructuredLoggingMiddleware (backward-compat alias for RequestContextMiddleware)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from quadkit.web.middleware.request_context import RequestContextMiddleware

StructuredLoggingMiddleware = RequestContextMiddleware


async def _plain_inner(scope, receive, send) -> None:
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


class TestStructuredLoggingMiddleware:
    def test_is_alias_for_request_context_middleware(self) -> None:
        assert StructuredLoggingMiddleware is RequestContextMiddleware  # type: ignore[has-type]

    def test_http_request_passes_through(self) -> None:
        mock_registry = MagicMock()
        mock_registry.set_typed.return_value = MagicMock()
        mock_context = MagicMock()
        mock_context.registry = mock_registry

        with patch(
            "quadkit.web.middleware.request_context.create_default_context",
            return_value=mock_context,
        ):
            app = StructuredLoggingMiddleware(_plain_inner)
            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200
            assert response.text == "ok"

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through_without_context(self) -> None:
        called = []

        async def inner(scope, receive, send) -> None:
            called.append(scope["type"])

        middleware = StructuredLoggingMiddleware(inner)
        await middleware({"type": "websocket"}, None, None)

        assert "websocket" in called
