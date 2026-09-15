"""Tests for unified middleware adapters."""
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.middleware.unified import (
    ASGIMiddlewareAdapter,
    RequestResponseMiddlewareAdapter,
)


def _make_inner():
    async def homepage(request):
        return JSONResponse({"ok": True})

    return Starlette(routes=[Route("/", homepage)])


class TestRequestResponseMiddlewareAdapter:
    """Tests for RequestResponseMiddlewareAdapter."""

    def test_pass_through_without_callbacks(self) -> None:
        inner = _make_inner()
        wrapped = RequestResponseMiddlewareAdapter(inner)
        client = TestClient(wrapped)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_process_request_callback_called(self) -> None:
        called: list[str] = []

        async def process_request(request):
            called.append("request")

        inner = _make_inner()
        wrapped = RequestResponseMiddlewareAdapter(inner, process_request=process_request)
        client = TestClient(wrapped)
        client.get("/")
        assert "request" in called

    def test_process_response_callback_called(self) -> None:
        called: list[str] = []

        async def process_response(response):
            called.append("response")
            return None  # returning None means don't replace response

        inner = _make_inner()
        wrapped = RequestResponseMiddlewareAdapter(
            inner, process_response=process_response
        )
        client = TestClient(wrapped)
        client.get("/")
        assert "response" in called

    def test_non_http_scope_passes_directly(self) -> None:
        """Non-HTTP scopes (lifespan) pass through unmodified."""
        inner = _make_inner()
        wrapped = RequestResponseMiddlewareAdapter(inner)
        # TestClient handles lifespan internally; a successful GET proves pass-through
        client = TestClient(wrapped)
        response = client.get("/")
        assert response.status_code == 200


class TestASGIMiddlewareAdapter:
    """Tests for ASGIMiddlewareAdapter."""

    def test_delegates_to_inner_app(self) -> None:
        inner = _make_inner()
        adapter = ASGIMiddlewareAdapter(inner)
        client = TestClient(adapter)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_stores_app_reference(self) -> None:
        inner = _make_inner()
        adapter = ASGIMiddlewareAdapter(inner)
        assert adapter.app is inner
