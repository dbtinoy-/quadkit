"""Exercise the real ai-assistant composition root through HTTP — the
fake client is bound through the provider, not monkeypatching."""

from __future__ import annotations

import httpx


async def test_chat_roundtrip_uses_bound_client(
    client: httpx.AsyncClient, fake: object
) -> None:
    response = await client.post("/chat", json={"message": "summarise quadkit"})
    assert response.status_code == 201
    assert response.json() == {"answer": "echo: summarise quadkit"}
    assert fake.calls[0][-1] == {"role": "user", "content": "summarise quadkit"}


async def test_history_is_forwarded(client: httpx.AsyncClient, fake: object) -> None:
    history = [{"role": "user", "content": "earlier"}]
    response = await client.post("/chat", json={"message": "now", "history": history})
    assert response.status_code == 201
    assert fake.calls[0][0] == {"role": "user", "content": "earlier"}


async def test_empty_message_is_a_422_problem(client: httpx.AsyncClient) -> None:
    response = await client.post("/chat", json={"message": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert "message" in body["detail"].lower()


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "ai-assistant"
    assert isinstance(body["endpoints"], list) and body["endpoints"]
