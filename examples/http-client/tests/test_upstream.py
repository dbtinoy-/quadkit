"""Exercise the real http-client composition root through HTTP.

These round trips prove the outbound-client contract end to end: the demo's
``quadkit-http`` client makes a genuine loopback call to the in-process mock
upstream and surfaces the real status and body — no mocks at the client
level, only the "third party" is simulated.
"""

from __future__ import annotations

import httpx


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "http-client"
    assert "GET /upstream/echo" in body["endpoints"]


async def test_echo_is_a_real_upstream_roundtrip(client: httpx.AsyncClient) -> None:
    response = await client.get("/upstream/echo")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 200
    # the upstream echoed the request the quadkit-http client actually made
    assert body["json"]["method"] == "GET"
    assert body["json"]["path"] == "/echo"


async def test_status_route_reports_the_real_upstream_status(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/upstream/status/201")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 201
    assert body["json"]["requested_status"] == 201
