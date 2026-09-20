"""Tests for middleware/access_log.py — AccessLogMiddleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from quadkit.web.middleware.access_log import AccessLogMiddleware


async def _plain_inner(scope, receive, send) -> None:
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


async def _error_inner(scope, receive, send) -> None:
    response = Response("err", status_code=500)
    await response(scope, receive, send)


async def _not_found_inner(scope, receive, send) -> None:
    response = Response("not found", status_code=404)
    await response(scope, receive, send)


class TestAccessLogMiddlewareInit:
    def test_defaults(self) -> None:
        mw = AccessLogMiddleware(_plain_inner)
        assert mw.app is _plain_inner
        assert mw._ctx is None
        assert "/health" in mw.exclude_paths or "/healthz" in mw.exclude_paths

    def test_custom_exclude_paths(self) -> None:
        mw = AccessLogMiddleware(_plain_inner, exclude_paths=["/metrics"])
        assert "/metrics" in mw.exclude_paths

    def test_custom_context(self) -> None:
        ctx = MagicMock()
        mw = AccessLogMiddleware(_plain_inner, ctx=ctx)
        assert mw._ctx is ctx


class TestAccessLogMiddlewareCall:
    def test_logs_successful_request(self) -> None:
        mw = AccessLogMiddleware(_plain_inner)
        client = TestClient(mw)
        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            response = client.get("/api/data")
        assert response.status_code == 200
        mock_logger.info.assert_called()

    def test_logs_4xx_as_warning(self) -> None:
        mw = AccessLogMiddleware(_not_found_inner)
        client = TestClient(mw)
        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            client.get("/missing")
        mock_logger.warning.assert_called()

    def test_logs_5xx_as_error(self) -> None:
        mw = AccessLogMiddleware(_error_inner)
        client = TestClient(mw, raise_server_exceptions=False)
        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            client.get("/crash")
        mock_logger.error.assert_called()

    def test_excluded_path_skips_logging(self) -> None:
        mw = AccessLogMiddleware(_plain_inner, exclude_paths=["/health"])
        client = TestClient(mw)
        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            response = client.get("/health")
        assert response.status_code == 200
        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        called = []

        async def inner(scope, receive, send) -> None:
            called.append(scope["type"])

        mw = AccessLogMiddleware(inner)
        await mw({"type": "websocket"}, None, None)
        assert "websocket" in called

    def test_includes_request_id_when_context_provides_it(self) -> None:
        ctx = MagicMock()
        ctx.get.return_value = "req_abc123"
        mw = AccessLogMiddleware(_plain_inner, ctx=ctx)
        client = TestClient(mw)
        log_kwargs_captured = {}

        def capture_log(event: str, **kwargs: object) -> None:
            log_kwargs_captured.update(kwargs)

        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            mock_logger.info.side_effect = capture_log
            client.get("/api/data")

        assert log_kwargs_captured.get("request_id") == "req_abc123"

    def test_no_request_id_when_context_is_none(self) -> None:
        mw = AccessLogMiddleware(_plain_inner)  # ctx=None
        client = TestClient(mw)
        log_kwargs_captured = {}

        def capture_log(event: str, **kwargs: object) -> None:
            log_kwargs_captured.update(kwargs)

        with patch("quadkit.web.middleware.access_log.logger") as mock_logger:
            mock_logger.info.side_effect = capture_log
            client.get("/api/data")

        assert "request_id" not in log_kwargs_captured
