"""Exercise the real background-worker composition root through HTTP —
work flows through the provider lifecycle, not around it."""

from __future__ import annotations

import asyncio

import httpx


async def test_submit_is_accepted_and_processed(client: httpx.AsyncClient) -> None:
    posted = await client.post("/tasks", json={"duration": 0.01})
    assert posted.status_code == 202
    assert posted.json()["accepted"] is True

    # Give the loop a beat to drain, then assert counters moved.
    await asyncio.sleep(0.2)
    stats = await client.get("/stats")
    assert stats.json()["enqueued"] == 1
    assert stats.json()["processed"] == 1
    assert stats.json()["failed"] == 0


async def test_multiple_tasks_share_bounded_pool(client: httpx.AsyncClient) -> None:
    for _ in range(5):
        await client.post("/tasks", json={"duration": 0.02})
    await asyncio.sleep(0.5)
    stats = await client.get("/stats")
    assert stats.json()["processed"] == 5
    assert stats.json()["pending"] == 0


async def test_failed_tasks_are_counted_and_workers_survive(client: httpx.AsyncClient) -> None:
    """Failure injection: a raising task must not kill the pool."""
    await client.post("/tasks", json={"fail": True})
    await client.post("/tasks", json={"duration": 0.01})
    await asyncio.sleep(0.2)
    stats = (await client.get("/stats")).json()
    assert stats["failed"] == 1
    # The pool is still alive and kept processing after the failure.
    assert stats["processed"] == 1


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "background-worker"
    assert isinstance(body["endpoints"], list) and body["endpoints"]
