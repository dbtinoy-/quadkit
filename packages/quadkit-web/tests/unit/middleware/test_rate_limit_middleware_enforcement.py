"""Tests: RateLimitMiddleware enforces declared rules and default limits (F1)."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.contracts.exceptions import RateLimitError
from quadkit.web.config import RateLimitConfig, RateLimitRuleConfig
from quadkit.web.integrations.rate_limit import RateLimitIntegration
from quadkit.web.middleware.rate_limit import RateLimiter, RateLimitMiddleware


def _app(rate_config: RateLimitConfig) -> Starlette:
    async def ok(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/api/expensive", endpoint=ok)])
    limiter = RateLimiter()
    app.add_exception_handler(RateLimitError, RateLimitIntegration._rate_limit_handler)
    app.add_middleware(RateLimitMiddleware, rate_limiter=limiter, config=rate_config)
    return app


class TestRateLimitMiddlewareEnforces:
    def test_rule_from_rules_dict_enforced(self) -> None:
        config = RateLimitConfig(
            enabled=True,
            rules={"/api/expensive": RateLimitRuleConfig(requests=2, window=60)},
        )
        client = TestClient(_app(config), raise_server_exceptions=False)
        assert client.get("/api/expensive").status_code == 200
        assert client.get("/api/expensive").status_code == 200
        r3 = client.get("/api/expensive")
        assert r3.status_code == 429
        assert r3.headers.get("Retry-After") is not None

    def test_default_limit_enforced_when_no_rules_declared(self) -> None:
        config = RateLimitConfig(enabled=True, default_limit=1, default_window=60)
        client = TestClient(_app(config), raise_server_exceptions=False)
        assert client.get("/api/expensive").status_code == 200
        assert client.get("/api/expensive").status_code == 429

    def test_disabled_config_passes_through(self) -> None:
        config = RateLimitConfig(enabled=False)
        client = TestClient(_app(config), raise_server_exceptions=False)
        assert client.get("/api/expensive").status_code == 200
        assert client.get("/api/expensive").status_code == 200

    def test_headers_stamped_after_enforcement(self) -> None:
        config = RateLimitConfig(enabled=True, default_limit=5, default_window=60)
        client = TestClient(_app(config), raise_server_exceptions=False)
        r = client.get("/api/expensive")
        assert r.status_code == 200
        assert r.headers.get("x-ratelimit-remaining") == "4"
        assert r.headers.get("x-ratelimit-limit") == "5"

    def test_whitelisted_ip_skips_enforcement(self) -> None:
        config = RateLimitConfig(
            enabled=True,
            default_limit=1,
            default_window=60,
            whitelist_ips=["testclient"],
        )
        client = TestClient(_app(config), raise_server_exceptions=False)
        assert client.get("/api/expensive").status_code == 200
        assert client.get("/api/expensive").status_code == 200