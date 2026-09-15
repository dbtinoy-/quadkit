"""Tests for DebugHtmlErrorRenderer, DefaultExceptionFilter (debug mode),
and FilterPipeline (debug mode fallback).

Covers:
- _accepts_html() content-negotiation logic
- DebugHtmlErrorRenderer.should_render() delegates to _accepts_html
- DebugHtmlErrorRenderer.render() produces valid HTML with key elements
- DebugHtmlErrorRenderer.render() redacts sensitive headers
- DebugHtmlErrorRenderer.render() shows traceback when available
- DebugHtmlErrorRenderer.render() shows exception chain
- DefaultExceptionFilter(debug=False) always returns JSON
- DefaultExceptionFilter(debug=True) returns HTML for browser clients
- DefaultExceptionFilter(debug=True) returns JSON for API clients
- FilterPipeline(debug=True) uses HTML fallback for unhandled exceptions
- FilterPipeline(debug=False) uses JSON fallback regardless of Accept header
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_request(accept: str = "text/html,*/*;q=0.9", method: str = "GET",
                  url: str = "http://localhost/test",
                  headers: dict | None = None) -> MagicMock:
    """Build a minimal mock Starlette request."""
    req = MagicMock()
    req.method = method
    req.url = url
    hdr = {"accept": accept, **(headers or {})}
    req.headers = MagicMock()
    req.headers.get = lambda k, d="": hdr.get(k, d)
    req.headers.items = lambda: list(hdr.items())
    req.query_params = MagicMock()
    req.query_params.items = lambda: []
    return req


def _raise_with_tb(msg: str = "boom") -> Exception:
    """Return an exception with a real traceback."""
    try:
        raise ValueError(msg)
    except ValueError as exc:
        return exc


# ─────────────────────────────────────────────────────────────────────────────
# _accepts_html
# ─────────────────────────────────────────────────────────────────────────────


class TestAcceptsHtml:
    def test_browser_accept_header(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        assert _accepts_html(req) is True

    def test_json_only_accept_header(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("application/json")
        assert _accepts_html(req) is False

    def test_no_accept_header(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("")
        assert _accepts_html(req) is False

    def test_wildcard_accept_without_json(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("*/*")
        # "*/*" maps to html_q = 1.0, json_q = 0.0 → True
        assert _accepts_html(req) is True

    def test_html_with_lower_q_than_json(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("application/json;q=1.0,text/html;q=0.5")
        assert _accepts_html(req) is False

    def test_equal_q_values_html_accepted(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        req = _make_request("text/html;q=1.0,application/json;q=1.0")
        assert _accepts_html(req) is True

    def test_bad_request_object_returns_false(self):
        from quadkit.web.errors.html_error_renderer import _accepts_html

        assert _accepts_html(None) is False  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# DebugHtmlErrorRenderer.render()
# ─────────────────────────────────────────────────────────────────────────────


class TestDebugHtmlErrorRenderer:
    def _renderer(self):
        from quadkit.web.errors.html_error_renderer import DebugHtmlErrorRenderer
        return DebugHtmlErrorRenderer()

    def test_returns_html_response(self):
        from starlette.responses import HTMLResponse

        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb("test error")
        resp = renderer.render(exc, req, status_code=500)
        assert isinstance(resp, HTMLResponse)

    def test_status_code_propagated(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=404)
        assert resp.status_code == 404

    def test_html_contains_exception_type(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb("test error")
        resp = renderer.render(exc, req, status_code=500)
        assert b"ValueError" in resp.body

    def test_html_contains_exception_message(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb("unique_error_message_xyz")
        resp = renderer.render(exc, req, status_code=500)
        assert b"unique_error_message_xyz" in resp.body

    def test_html_contains_traceback_frame(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        # Should include the test function name as a frame
        assert b"_raise_with_tb" in resp.body

    def test_html_contains_request_method(self):
        renderer = self._renderer()
        req = _make_request(method="POST")
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        assert b"POST" in resp.body

    def test_html_contains_request_url(self):
        renderer = self._renderer()
        req = _make_request(url="http://localhost/api/test-path")
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        assert b"/api/test-path" in resp.body

    def test_sensitive_headers_are_redacted(self):
        renderer = self._renderer()
        req = _make_request(headers={"authorization": "Bearer secret-token"})
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=401)
        assert b"secret-token" not in resp.body
        assert b"REDACTED" in resp.body

    def test_non_sensitive_headers_are_visible(self):
        renderer = self._renderer()
        req = _make_request(headers={"x-request-id": "req-abc-123"})
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        assert b"req-abc-123" in resp.body

    def test_exception_chain_shown(self):
        renderer = self._renderer()
        req = _make_request()
        try:
            try:
                raise TypeError("root cause")
            except TypeError as cause:
                raise RuntimeError("wrapped error") from cause
        except RuntimeError as exc:
            resp = renderer.render(exc, req, status_code=500)
        assert b"TypeError" in resp.body
        assert b"root cause" in resp.body

    def test_debug_marker_in_html(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        assert b"debug" in resp.body.lower()

    def test_valid_html_structure(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=500)
        body = resp.body
        assert b"<!DOCTYPE html>" in body
        assert b"<html" in body
        assert b"</html>" in body

    def test_custom_title_used(self):
        renderer = self._renderer()
        req = _make_request()
        exc = _raise_with_tb()
        resp = renderer.render(exc, req, status_code=400, title="Custom Error Title")
        assert b"Custom Error Title" in resp.body

    def test_should_render_browser(self):
        renderer = self._renderer()
        req = _make_request("text/html,*/*;q=0.9")
        assert renderer.should_render(req) is True

    def test_should_not_render_api_client(self):
        renderer = self._renderer()
        req = _make_request("application/json")
        assert renderer.should_render(req) is False


# ─────────────────────────────────────────────────────────────────────────────
# DefaultExceptionFilter — debug=False (production mode)
# ─────────────────────────────────────────────────────────────────────────────


class TestDefaultExceptionFilterProd:
    @pytest.mark.asyncio
    async def test_http_error_returns_json(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter
        from quadkit.web.transport.responses import JSONResponse

        f = DefaultExceptionFilter(debug=False)
        req = _make_request("text/html,*/*;q=0.9")
        exc = HTTPError(400, "bad request")
        resp = await f.handle(exc, req)
        assert isinstance(resp, JSONResponse)

    @pytest.mark.asyncio
    async def test_domain_error_returns_json(self):
        from quadkit.contracts.exceptions.domain import NotFoundError
        from quadkit.web.filters.builtin import DefaultExceptionFilter
        from quadkit.web.transport.responses import JSONResponse

        f = DefaultExceptionFilter(debug=False)
        req = _make_request("text/html,*/*;q=0.9")
        exc = NotFoundError("Item")
        resp = await f.handle(exc, req)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_json_body_has_success_false(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=False)
        req = _make_request("application/json")
        exc = HTTPError(404, "not found")
        resp = await f.handle(exc, req)
        import json
        body = json.loads(resp.body)
        assert body["status"] == 404


# ─────────────────────────────────────────────────────────────────────────────
# DefaultExceptionFilter — debug=True
# ─────────────────────────────────────────────────────────────────────────────


class TestDefaultExceptionFilterDebug:
    @pytest.mark.asyncio
    async def test_browser_client_gets_html_for_http_error(self):
        from starlette.responses import HTMLResponse

        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=True)
        req = _make_request("text/html,*/*;q=0.9")
        exc = HTTPError(500, "unexpected error")
        resp = await f.handle(exc, req)
        assert isinstance(resp, HTMLResponse)

    @pytest.mark.asyncio
    async def test_api_client_still_gets_json_in_debug(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter
        from quadkit.web.transport.responses import JSONResponse

        f = DefaultExceptionFilter(debug=True)
        req = _make_request("application/json")
        exc = HTTPError(400, "bad request")
        resp = await f.handle(exc, req)
        assert isinstance(resp, JSONResponse)

    @pytest.mark.asyncio
    async def test_browser_gets_html_for_domain_not_found(self):
        from starlette.responses import HTMLResponse

        from quadkit.contracts.exceptions.domain import NotFoundError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=True)
        req = _make_request("text/html,*/*;q=0.9")
        exc = NotFoundError("User")
        resp = await f.handle(exc, req)
        assert isinstance(resp, HTMLResponse)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_html_status_code_matches_http_error(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=True)
        req = _make_request("text/html,*/*;q=0.9")
        exc = HTTPError(403, "forbidden")
        resp = await f.handle(exc, req)
        assert resp.status_code == 403

    def test_can_handle_returns_true_for_http_error(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=True)
        assert f.can_handle(HTTPError(500, "error")) is True

    def test_can_handle_returns_true_for_domain_error(self):
        from quadkit.contracts.exceptions.domain import DomainError
        from quadkit.web.filters.builtin import DefaultExceptionFilter

        f = DefaultExceptionFilter(debug=True)
        assert f.can_handle(DomainError("some domain error")) is True


# ─────────────────────────────────────────────────────────────────────────────
# FilterPipeline debug fallback
# ─────────────────────────────────────────────────────────────────────────────


class TestFilterPipelineDebugFallback:
    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_json_in_prod(self):
        from quadkit.web.filters.pipeline import FilterPipeline
        from quadkit.web.transport.responses import JSONResponse

        pipeline = FilterPipeline(debug=False)
        req = _make_request("text/html,*/*;q=0.9")
        # RuntimeError is not handled by any filter
        exc = RuntimeError("unhandled")
        resp = await pipeline.handle(exc, req)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_html_in_debug_for_browser(self):
        from starlette.responses import HTMLResponse

        from quadkit.web.filters.pipeline import FilterPipeline

        pipeline = FilterPipeline(debug=True)
        req = _make_request("text/html,*/*;q=0.9")
        exc = _raise_with_tb("unhandled pipeline error")
        resp = await pipeline.handle(exc, req)
        assert isinstance(resp, HTMLResponse)
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_json_in_debug_for_api_client(self):
        from quadkit.web.filters.pipeline import FilterPipeline
        from quadkit.web.transport.responses import JSONResponse

        pipeline = FilterPipeline(debug=True)
        req = _make_request("application/json")
        exc = _raise_with_tb("unhandled")
        resp = await pipeline.handle(exc, req)
        assert isinstance(resp, JSONResponse)

    @pytest.mark.asyncio
    async def test_handled_exception_bypasses_debug_fallback(self):
        from quadkit.web.exceptions import HTTPError
        from quadkit.web.filters.builtin import DefaultExceptionFilter
        from quadkit.web.filters.pipeline import FilterPipeline
        from quadkit.web.transport.responses import JSONResponse

        # debug=True but filter handles it with a JSON response
        pipeline = FilterPipeline(debug=True)
        pipeline.add_filter(DefaultExceptionFilter(debug=False))  # returns JSON
        req = _make_request("application/json")
        exc = HTTPError(400, "bad request")
        resp = await pipeline.handle(exc, req)
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 400
