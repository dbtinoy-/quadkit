"""Tests for the web security CORS implementation."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.security.config import CORSConfig
from quadkit.web.security.cors.middleware import CORSMiddleware


def _make_app(config: CORSConfig) -> TestClient:
    """Build a TestClient backed by web CORSMiddleware wrapping a trivial app."""

    async def homepage(request):
        return JSONResponse({"ok": True})

    inner = Starlette(routes=[Route("/", homepage)])
    return TestClient(
        CORSMiddleware(inner, config=config), raise_server_exceptions=False
    )


class TestSecurityCORSMiddlewareWorks:
    """Verify quadkit-web's HTTP CORS middleware works end-to-end."""

    def test_allowed_origin_gets_cors_headers(self) -> None:
        """Test allowed origin receives CORS headers."""
        config = CORSConfig(
            allowed_origins=["https://myapp.com"],
            allow_credentials=True,
        )
        client = _make_app(config)

        response = client.get("/", headers={"origin": "https://myapp.com"})

        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin") == "https://myapp.com"
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_disallowed_origin_no_cors_headers(self) -> None:
        """Test disallowed origin does not get CORS headers."""
        config = CORSConfig(
            allowed_origins=["https://myapp.com"],
        )
        client = _make_app(config)

        response = client.get("/", headers={"origin": "https://evil.com"})

        assert response.status_code == 200
        # No ACAO header should be set for disallowed origin
        acao = response.headers.get("access-control-allow-origin", "")
        assert acao == ""

    def test_wildcard_origin_with_no_credentials(self) -> None:
        """Test wildcard origins without credentials."""
        config = CORSConfig(
            allowed_origins=["*"],
            allow_credentials=False,
        )
        client = _make_app(config)

        response = client.get("/", headers={"origin": "https://any.com"})

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"

    def test_preflight_request_succeeds(self) -> None:
        """Test OPTIONS preflight request is handled."""
        config = CORSConfig(
            allowed_origins=["https://myapp.com"],
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type", "X-Custom-Header"],
        )
        client = _make_app(config)

        response = client.options(
            "/",
            headers={
                "origin": "https://myapp.com",
                "access-control-request-method": "POST",
            },
        )

        assert response.status_code == 204
        assert response.headers.get("access-control-allow-methods") == "GET, POST, PUT"
        assert (
            response.headers.get("access-control-allow-origin") == "https://myapp.com"
        )


__all__ = ["TestSecurityCORSMiddlewareWorks"]
