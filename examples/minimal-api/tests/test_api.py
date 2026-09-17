"""Exercise the real minimal-api composition root through HTTP."""

from __future__ import annotations

import asyncio

import httpx


async def test_hello_returns_configured_greeting(client: httpx.AsyncClient) -> None:
    response = await client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "hello, quadkit"}


async def test_echo_roundtrips_body(client: httpx.AsyncClient) -> None:
    response = await client.post("/echo", json={"hello": "quadkit"})
    assert response.status_code == 201
    assert response.json() == {"you_sent": {"hello": "quadkit"}}


async def test_unknown_route_is_problem_detail(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "minimal-api"
    assert isinstance(body["endpoints"], list) and body["endpoints"]


async def test_concurrent_requests_do_not_bleed_state(client: httpx.AsyncClient) -> None:
    """Concurrency exercise: 50 mixed in-flight requests, all independent."""

    async def one(i: int) -> object:
        if i % 2:
            response = await client.get("/hello")
            return response.json()
        response = await client.post("/echo", json={"n": i})
        return response.json()["you_sent"]["n"]

    results = await asyncio.gather(*(one(i) for i in range(50)))
    for i, result in enumerate(results):
        expected = {"message": "hello, quadkit"} if i % 2 else i
        assert result == expected
