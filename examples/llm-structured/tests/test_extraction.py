"""Exercise the real ``quadkit-ai-llm`` structured output composition root."""

from __future__ import annotations

import httpx


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "llm-structured"
    assert "POST /extract" in body["endpoints"]


async def test_extract_parses_schema_caches_repeat_and_tracks_cost(
    client: httpx.AsyncClient,
) -> None:
    note = "URGENT: Checkout payment capture failing for EU cards"

    first = await client.post("/extract", json={"text": note})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["cached"] is False
    assert first_body["brief"]["category"] == "incident"
    assert first_body["brief"]["severity"] == "high"
    assert first_body["estimated_cost_usd"] > 0

    second = await client.post("/extract", json={"text": note})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["cached"] is True
    assert second_body["brief"] == first_body["brief"]

    stats = await client.get("/stats")
    assert stats.status_code == 200
    stats_body = stats.json()
    assert stats_body["extractions"] == 1
    assert stats_body["cache"]["hits"] == 1


async def test_blank_text_returns_validation_problem_detail(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/extract", json={"text": "   "})
    assert response.status_code == 422
