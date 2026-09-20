"""Assembly pins for the default middleware stack.

Pins the plans/09172026 request-path findings (R-01..R-04):

- ``DIScopeMiddleware`` is registered exactly once per application: the
  native stack built at Starlette construction is the single source of
  truth and ``MiddlewareSetup.configure`` must not re-add it (R-01).
- Exactly one DI scope is created and disposed per request (R-02).
- One request identity per request: the ``x-request-id`` response header,
  ``request.state.request_id`` as seen by handlers, and the inbound header
  (when present) all agree (R-03 / H-05).
- ``WebHooksMiddleware`` passes through untouched — same ``send`` callable,
  no wrapper — when no hook registry is configured (R-04).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from starlette.requests import Request
from starlette.testclient import TestClient

from quadkit.di.container import Container
import quadkit.di.container.scope as scope_module
from quadkit.web import Controller, get
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.middleware.hooks import WebHooksMiddleware


class ProbeController(Controller):
    """Echoes the request identity it observes, for assertion."""

    @get("/assembly-probe")
    async def probe(self, request: Request) -> dict:
        return {"request_id": request.state.request_id}


def _boot_provider() -> WebProvider:
    """Boot a WebProvider with the probe controller and default config."""
    provider = WebProvider(
        controllers=[ProbeController],
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
    )
    container = Container()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(provider.register(container))
        loop.run_until_complete(provider.boot(container))
    finally:
        loop.close()
    return provider


class TestSingleRegistration:
    """R-01 — the DI-scope layer appears exactly once in the final stack."""

    def test_di_scope_registered_exactly_once(self) -> None:
        provider = _boot_provider()
        assert provider.starlette is not None
        names = [mw.cls.__name__ for mw in provider.starlette.user_middleware]

        assert names.count("DIScopeMiddleware") == 1, (
            f"DIScopeMiddleware must appear exactly once, got {names.count('DIScopeMiddleware')} "
            f"in {names}"
        )
        # Sanity: the configure() path did run and contributed its layers.
        assert "RequestContextMiddleware" in names
        assert "WebHooksMiddleware" in names


class TestOneScopePerRequest:
    """R-02 — one Scope creation and one disposal per request."""

    def test_one_scope_created_and_disposed_per_request(self, monkeypatch) -> None:
        provider = _boot_provider()
        counts = {"created": 0, "disposed": 0}

        orig_init = scope_module.Scope.__init__
        orig_dispose = scope_module.Scope.dispose

        def counting_init(self: Any, *args: Any, **kwargs: Any) -> None:
            counts["created"] += 1
            orig_init(self, *args, **kwargs)

        async def counting_dispose(self: Any) -> None:
            counts["disposed"] += 1
            await orig_dispose(self)

        # Patch after boot so startup wiring is not counted.
        monkeypatch.setattr(scope_module.Scope, "__init__", counting_init)
        monkeypatch.setattr(scope_module.Scope, "dispose", counting_dispose)

        client = TestClient(provider.starlette)
        response = client.get("/assembly-probe")

        assert response.status_code == 200
        assert counts == {"created": 1, "disposed": 1}, (
            f"expected exactly one scope per request, got {counts}"
        )


class TestRequestIdUnification:
    """R-03 / H-05 — header, handler-visible state, and inbound id agree."""

    def test_generated_id_is_uniform(self) -> None:
        provider = _boot_provider()
        client = TestClient(provider.starlette)

        response = client.get("/assembly-probe")

        assert response.status_code == 200
        header_id = response.headers["x-request-id"]
        # Unified format: req_<12 hex chars>
        assert header_id.startswith("req_"), (
            f"unexpected request id format: {header_id!r}"
        )
        assert len(header_id) == 16, f"unexpected request id length: {header_id!r}"
        assert response.json()["request_id"] == header_id, (
            "handler-visible request.state.request_id must match the response header"
        )

    def test_inbound_id_is_reused_uniformly(self) -> None:
        provider = _boot_provider()
        client = TestClient(provider.starlette)

        response = client.get(
            "/assembly-probe", headers={"X-Request-ID": "client-id-42"}
        )

        assert response.status_code == 200
        assert response.headers["x-request-id"] == "client-id-42"
        assert response.json()["request_id"] == "client-id-42"

    def test_distinct_ids_across_requests(self) -> None:
        provider = _boot_provider()
        client = TestClient(provider.starlette)

        first = client.get("/assembly-probe")
        second = client.get("/assembly-probe")

        assert first.headers["x-request-id"] != second.headers["x-request-id"]


class TestIdlePassthrough:
    """R-04 — unconfigured hook emission costs nothing."""

    async def test_idle_hooks_forward_original_send(self) -> None:
        received: dict[str, Any] = {}

        async def inner_app(scope: Any, receive: Any, send: Any) -> None:
            received["send"] = send

        async def receive() -> dict[str, Any]:  # pragma: no cover - unused
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Any) -> None:  # pragma: no cover - unused
            pass

        middleware = WebHooksMiddleware(app=inner_app, hooks=None)
        await middleware({"type": "http", "path": "/", "method": "GET"}, receive, send)

        assert received["send"] is send, (
            "idle WebHooksMiddleware must forward the original send callable"
        )

    async def test_configured_hooks_still_wrap(self) -> None:
        """With a registry present the wrapping behaviour is unchanged."""
        from unittest.mock import AsyncMock

        registry = AsyncMock()
        registry.call_action = AsyncMock(return_value=None)
        wrapped: dict[str, Any] = {}

        async def inner_app(scope: Any, receive: Any, send_wrapped: Any) -> None:
            wrapped["send"] = send_wrapped

        async def receive() -> dict[str, Any]:  # pragma: no cover - unused
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Any) -> None:  # pragma: no cover - unused
            pass

        middleware = WebHooksMiddleware(app=inner_app, hooks=registry)
        await middleware({"type": "http", "path": "/", "method": "GET"}, receive, send)

        assert wrapped["send"] is not send
        called_hooks = [call.args[0] for call in registry.call_action.await_args_list]
        assert "request.received" in called_hooks


__all__ = [
    "TestSingleRegistration",
    "TestOneScopePerRequest",
    "TestRequestIdUnification",
    "TestIdlePassthrough",
]


class TestInboundRequestIdSanitization:
    """plans/09172026 H-01 — inbound request ids are client-controlled.

    Only short URL-safe tokens are accepted; CRLF, control characters,
    oversized and non-ascii values are dropped and a fresh id generated.
    The rejected value never reaches the response header or the state.
    """

    @staticmethod
    async def _drive(headers: list[tuple[bytes, bytes]]) -> dict[str, Any]:
        """Drive RequestContextMiddleware directly with a raw ASGI scope."""
        from quadkit.web.middleware.request_context import RequestContextMiddleware

        captured: dict[str, Any] = {}
        sent: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        async def inner(scope: Any, recv: Any, snd: Any) -> None:
            captured["state_request_id"] = scope.get("state", {}).get("request_id")
            await snd({"type": "http.response.start", "status": 200, "headers": []})
            await snd({"type": "http.response.body", "body": b""})

        middleware = RequestContextMiddleware(app=inner)
        scope = {"type": "http", "method": "GET", "path": "/", "headers": headers}
        await middleware(scope, receive, send)

        response_id = next(
            (
                value.decode()
                for key, value in sent[0].get("headers", [])
                if key == b"x-request-id"
            ),
            None,
        )
        captured["response_id"] = response_id
        return captured

    async def test_crlf_payload_rejected(self) -> None:
        result = await self._drive([(b"x-request-id", b"abc\r\nX-Injected: true")])
        assert result["response_id"] is not None
        assert result["response_id"].startswith("req_")
        assert result["state_request_id"] == result["response_id"]
        assert "\r" not in result["response_id"]

    async def test_control_characters_rejected(self) -> None:
        result = await self._drive([(b"x-request-id", b"id\x01\x02\x7f")])
        assert result["response_id"].startswith("req_")
        assert result["state_request_id"] == result["response_id"]

    async def test_oversized_payload_rejected(self) -> None:
        result = await self._drive([(b"x-request-id", b"A" * 10_000)])
        assert result["response_id"].startswith("req_")
        assert len(result["response_id"]) == 16

    async def test_malformed_utf8_rejected_without_crashing(self) -> None:
        """Bad header bytes must not raise (previously a 500)."""
        result = await self._drive([(b"x-request-id", b"\xc3\x28")])
        assert result["response_id"].startswith("req_")

    async def test_valid_ids_pass_through(self) -> None:
        result = await self._drive([(b"x-request-id", b"client-id_42-ABC")])
        assert result["response_id"] == "client-id_42-ABC"
        assert result["state_request_id"] == "client-id_42-ABC"

    async def test_boundary_length(self) -> None:
        ok = await self._drive([(b"x-request-id", b"a" * 64)])
        assert ok["response_id"] == "a" * 64
        too_long = await self._drive([(b"x-request-id", b"a" * 65)])
        assert too_long["response_id"].startswith("req_")


class TestSanitizeRequestId:
    """Unit table for the shared sanitizer."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            ("req_abc123", "req_abc123"),
            ("a" * 64, "a" * 64),
            ("a" * 65, None),
            ("with space", None),
            ("tab\tid", None),
            ("nl\nid", None),
            ("cr\r\nid", None),
            ("semi;id", None),
            ('quote"id', None),
            ("unicode-ünïcode", None),
            ("\ufffd", None),
        ],
    )
    def test_table(self, value: str | None, expected: str | None) -> None:
        from quadkit.web.middleware._headers import sanitize_request_id

        assert sanitize_request_id(value) == expected


class TestHostileRequestIdEndToEnd:
    """H-01 through the full default stack."""

    def test_oversized_inbound_id_gets_generated_id(self) -> None:
        provider = _boot_provider()
        client = TestClient(provider.starlette)

        response = client.get("/assembly-probe", headers={"X-Request-ID": "A" * 10_000})

        assert response.status_code == 200
        header_id = response.headers["x-request-id"]
        assert header_id.startswith("req_")
        assert len(header_id) == 16
        assert response.json()["request_id"] == header_id
