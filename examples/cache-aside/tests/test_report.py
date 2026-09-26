"""Exercise the real cache-aside composition root through HTTP.

These round trips prove the cache-aside contract end to end: the first read
computes, the second is served from ``quadkit-cache``, and an invalidate
forces a recompute — no mocks, the real DI container and cache backend.
"""

from __future__ import annotations

import httpx


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "cache-aside"
    assert "GET /report" in body["endpoints"]


async def test_first_read_computes_then_caches(client: httpx.AsyncClient) -> None:
    first = await client.get("/report")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["cached"] is False
    assert first_body["computes"] == 1

    second = await client.get("/report")
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["cached"] is True
    # served from cache: same payload, no second compute
    assert second_body["computed_at"] == first_body["computed_at"]
    assert second_body["computes"] == 1


async def test_invalidate_forces_a_recompute(client: httpx.AsyncClient) -> None:
    await client.get("/report")
    invalidated = await client.post("/report/invalidate")
    assert invalidated.status_code == 200
    assert invalidated.json() == {"invalidated": True}

    after = await client.get("/report")
    assert after.status_code == 200
    body = after.json()
    assert body["cached"] is False
    assert body["computes"] == 2
