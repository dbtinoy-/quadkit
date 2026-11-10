"""Unit tests for @rate_limit decorator ASGI request ContextVar & endpoint namespace isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from quadkit.contracts.exceptions import RateLimitError
from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.di import Container
from quadkit.web.middleware.rate_limit import (
    RateLimiter,
    rate_limit,
    reset_current_request,
    set_current_request,
)


def _make_request(
    limiter: RateLimiter,
    path: str = "/api/v1/auth/dev-login",
    client_ip: str = "127.0.0.1",
) -> Request:
    container = Container()
    container.singleton(WebRateLimiterProtocol, instance=limiter)
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "headers": [],
        "client": (client_ip, 50000),
        "app": object(),
        "state": {"container": container},
    }
    return Request(scope)


@dataclass
class _LoginDTO:
    email: str


@pytest.mark.asyncio
async def test_rate_limit_decorator_enforces_on_dto_only_endpoint_via_contextvar() -> (
    None
):
    """DTO-only controller methods without a Request parameter still enforce @rate_limit."""
    limiter = RateLimiter()

    class _AuthController:
        @rate_limit(max_requests=2, window_seconds=60)
        async def dev_login(self, body: _LoginDTO) -> JSONResponse:
            return JSONResponse({"email": body.email})

        @rate_limit(max_requests=3, window_seconds=60)
        async def logout(self, body: _LoginDTO) -> JSONResponse:
            return JSONResponse({"ok": body.email})

    ctrl = _AuthController()
    req = _make_request(limiter)

    token = set_current_request(req)
    try:
        r1 = await ctrl.dev_login(_LoginDTO(email="a@example.com"))
        r2 = await ctrl.dev_login(_LoginDTO(email="a@example.com"))
        with pytest.raises(RateLimitError):
            await ctrl.dev_login(_LoginDTO(email="a@example.com"))
        # Independent endpoint has its own namespace bucket even after dev_login hits RateLimitError
        out_res = await ctrl.logout(_LoginDTO(email="a@example.com"))
    finally:
        reset_current_request(token)

    assert [r1.status_code, r2.status_code] == [200, 200]
    assert out_res.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_decorator_accepts_underscore_request_kwarg() -> None:
    """_request keyword argument is detected cleanly when no ContextVar is active."""
    limiter = RateLimiter()

    @rate_limit(max_requests=1, window_seconds=60)
    async def endpoint(_request: Request) -> dict[str, bool]:
        return {"ok": True}

    req = _make_request(limiter, "/api/ping")

    first = await endpoint(_request=req)
    assert first == {"ok": True}
    with pytest.raises(RateLimitError):
        await endpoint(_request=req)
