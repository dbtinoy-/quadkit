"""Pin the gzip compression wiring behind ``web.compression_enabled``.

`CompressionMiddleware` shipped with the package but was never mounted, so
``web.compression_enabled`` — documented as "enable response compression" —
had no effect on any response. These tests boot the real stack and assert the
two directions of the switch, so a regression that unmounts the middleware
fails here instead of silently shipping an uncompressed default.
"""

from __future__ import annotations

from typing import Any

import pytest
from quadkit.app.base import Application
from quadkit.web import Controller, get
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider
from starlette.testclient import TestClient

#: Larger than ``CompressionMiddleware``'s 1024-byte minimum.
_PAYLOAD_ITEMS = 200


class ProbeController(Controller):
    """One route returning a JSON body worth compressing."""

    @get("/probe")
    async def probe(self) -> dict[str, Any]:
        return {"items": [f"row-{index}" for index in range(_PAYLOAD_ITEMS)]}


async def _booted_client(compression_enabled: bool) -> TestClient:
    """Boot a default web app with the compression switch at a known value."""
    app = Application(name="compression-wiring-probe")
    web = WebProvider(
        web_config=WebConfig(
            rate_limit=RateLimitConfig(enabled=False),
            compression_enabled=compression_enabled,
        ),
        controllers=[ProbeController],
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None
    return TestClient(web.starlette)


@pytest.mark.asyncio
async def test_gzip_is_served_when_compression_is_enabled() -> None:
    """A client that accepts gzip gets a compressed, decodable body."""
    client = await _booted_client(compression_enabled=True)

    with client:
        response = client.get("/probe", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    # httpx decodes the body on the way in, so the wire size is the proof:
    # the compressed payload is smaller than the JSON httpx hands back.
    wire_size = int(response.headers["content-length"])
    assert wire_size < len(response.content)
    assert b"row-199" in response.content


@pytest.mark.asyncio
async def test_compression_is_withheld_when_disabled() -> None:
    """``compression_enabled=False`` leaves the response uncompressed."""
    client = await _booted_client(compression_enabled=False)

    with client:
        response = client.get("/probe", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert b"row-199" in response.content


@pytest.mark.asyncio
async def test_a_client_without_gzip_gets_the_plain_body() -> None:
    """Compression is negotiated, never assumed."""
    client = await _booted_client(compression_enabled=True)

    with client:
        response = client.get("/probe", headers={"Accept-Encoding": "identity"})

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert b"row-199" in response.content
