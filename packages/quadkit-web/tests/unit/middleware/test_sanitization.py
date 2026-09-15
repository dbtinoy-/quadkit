"""Tests for middleware/sanitization.py — InputSanitizationMiddleware."""

from __future__ import annotations

import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from quadkit.web.middleware.sanitization import (
    InputSanitizationMiddleware,
    _sanitize_value,
)


class TestSanitizeValue:
    def test_clean_value_passes_through(self) -> None:
        assert _sanitize_value("hello world") == "hello world"

    def test_null_bytes_are_stripped(self) -> None:
        assert _sanitize_value("hel\x00lo") == "hello"

    def test_multiple_null_bytes_stripped(self) -> None:
        assert _sanitize_value("\x00\x00\x00") == ""

    def test_script_tag_returns_empty_string(self) -> None:
        assert _sanitize_value("<script>alert(1)</script>") == ""

    def test_script_tag_case_insensitive(self) -> None:
        assert _sanitize_value("<SCRIPT>alert(1)") == ""

    def test_javascript_uri_returns_empty_string(self) -> None:
        assert _sanitize_value("javascript:alert(1)") == ""

    def test_javascript_uri_with_spaces(self) -> None:
        assert _sanitize_value("javascript  :alert(1)") == ""

    def test_empty_string_passes(self) -> None:
        assert _sanitize_value("") == ""

    def test_normal_url_passes(self) -> None:
        value = "https://example.com/path"
        assert _sanitize_value(value) == value


class TestInputSanitizationMiddlewareInit:
    def test_defaults(self) -> None:
        async def app(scope, receive, send): ...
        mw = InputSanitizationMiddleware(app)
        assert mw.sanitize_query_params is True

    def test_can_disable_sanitization(self) -> None:
        async def app(scope, receive, send): ...
        mw = InputSanitizationMiddleware(app, sanitize_query_params=False)
        assert mw.sanitize_query_params is False


async def _query_echo_inner(scope, receive, send) -> None:
    """Inner app that echoes the query string back."""
    from starlette.requests import Request
    request = Request(scope, receive)
    qs = request.query_params.get("q", "")
    response = PlainTextResponse(qs)
    await response(scope, receive, send)


class TestInputSanitizationMiddlewareCall:
    def test_clean_query_passes_through(self) -> None:
        mw = InputSanitizationMiddleware(_query_echo_inner)
        client = TestClient(mw)
        response = client.get("/search?q=hello")
        assert response.status_code == 200
        assert "hello" in response.text

    def test_script_tag_in_query_is_sanitized(self) -> None:
        mw = InputSanitizationMiddleware(_query_echo_inner)
        client = TestClient(mw)
        response = client.get("/search?q=<script>alert(1)</script>")
        assert response.status_code == 200
        # Dangerous value should be emptied
        assert "script" not in response.text

    def test_null_bytes_in_query_are_stripped(self) -> None:
        mw = InputSanitizationMiddleware(_query_echo_inner)
        client = TestClient(mw)
        # Send null byte via percent encoding
        response = client.get("/search", params={"q": "hel\x00lo"})
        assert response.status_code == 200
        assert "\x00" not in response.text

    def test_sanitization_disabled_passes_raw(self) -> None:
        mw = InputSanitizationMiddleware(_query_echo_inner, sanitize_query_params=False)
        client = TestClient(mw)
        response = client.get("/search?q=hello")
        assert response.status_code == 200
        assert "hello" in response.text

    def test_no_query_string_passes_through(self) -> None:
        mw = InputSanitizationMiddleware(_query_echo_inner)
        client = TestClient(mw)
        response = client.get("/search")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        called = []

        async def inner(scope, receive, send) -> None:
            called.append(scope["type"])

        mw = InputSanitizationMiddleware(inner)
        await mw({"type": "websocket", "query_string": b""}, None, None)
        assert "websocket" in called
