"""Shared scope/app doubles for CSRF middleware tests."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.result import Ok
from quadkit.web.security.config import CSRFConfig
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

#: Any placeholder token value (unverifiable without a signing secret).
_RAW_TOKEN = "test-token-abc123"

#: Shared signing secret for verifiable-token tests.
_TEST_SECRET = "test-secret-key-32-bytes-long!!"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _make_scope(
    method: str = "GET",
    path: str = "/",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
    }


def _cookie_header(pairs: dict[str, str]) -> tuple[bytes, bytes]:
    cookie_str = "; ".join(f"{k}={v}" for k, v in pairs.items())
    return (b"cookie", cookie_str.encode())


def _make_app(*, called: list[bool] | None = None) -> AsyncMock:
    """Return a no-op ASGI app that records whether it was called."""
    store: list[bool] = called if called is not None else []

    async def _app(scope: Any, receive: Any, send: Any) -> None:  # noqa: ARG001
        store.append(True)

    return _app  # type: ignore[return-value]


async def _run(
    middleware: CSRFProtectionMiddleware, scope: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the middleware and collect sent messages."""
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(msg: dict[str, Any]) -> None:
        messages.append(msg)

    await middleware(scope, receive, send)
    return messages


# ---------------------------------------------------------------------------
# Non-HTTP passthrough

async def _responding_app(scope: Any, receive: Any, send: Any) -> None:  # noqa: ARG001
    """Minimal app that emits a 200 response so Set-Cookie can fire."""
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _signed_cookie_pairs(messages: list[dict[str, Any]]) -> dict[str, str]:
    """Parse Set-Cookie headers from the sent response messages."""
    pairs: dict[str, str] = {}
    for msg in messages:
        for name, value in msg.get("headers", []):
            if name == b"set-cookie":
                pairs.setdefault("set-cookie", value.decode())
    return pairs


