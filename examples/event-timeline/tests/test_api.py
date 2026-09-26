"""HTTP integration contract for quadkit-events + WebModule."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_exposes_offline_events_composition(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/events/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["offline"] is True
    assert data["event_store"] == "InMemoryEventStore"
    assert data["event_bus"] == "EventBusImpl"
    assert data["components"]["event_store"]["status"] == "healthy"
    assert data["components"]["event_bus"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_publish_preserves_store_order_and_notifies_subscriber(
    client: httpx.AsyncClient,
) -> None:
    first = await client.post(
        "/api/events/publish",
        json={"action": "open", "actor": "alice", "note": "cart ready"},
    )
    second = await client.post(
        "/api/events/publish",
        json={"action": "approve", "actor": "bob", "note": "looks good"},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["result"]["status"] == "enqueued"
    assert first.json()["event"]["sequence_number"] == 1
    assert second.json()["event"]["sequence_number"] == 2

    timeline = (await client.get("/api/events")).json()
    assert timeline["event_count"] == 2
    assert [event["action"] for event in timeline["events"]] == ["open", "approve"]
    assert [item["sequence_number"] for item in timeline["deliveries"]] == [1, 2]


@pytest.mark.asyncio
async def test_failure_is_reported_after_enqueue_and_does_not_stop_delivery(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/events/publish",
        json={"action": "fail", "actor": "test-runner"},
    )
    data = response.json()
    assert data["ok"] is True
    assert data["result"]["status"] == "enqueued"
    assert data["handler_failures"][0]["attempts"] == 4
    assert data["bus_dispatch_error_count"] == 1

    timeline = (await client.get("/api/events")).json()
    assert timeline["deliveries"][0]["status"] == "handled"
    assert timeline["handler_failures"][0]["status"] == "failed"
    assert timeline["bus_dispatch_error_count"] == 1

    health = (await client.get("/api/events/health")).json()
    assert health["status"] == "degraded"
    assert health["components"]["event_bus"]["details"]["dispatch_error_count"] == 1


@pytest.mark.asyncio
async def test_replay_reads_history_without_appending_duplicates(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/api/events/publish", json={"action": "open"})
    await client.post("/api/events/publish", json={"action": "approve"})
    response = await client.post("/api/events/replay")
    data = response.json()
    assert data["replay"]["count"] == 2
    assert data["replay"]["order"] == [1, 2]
    assert data["event_count"] == 2


@pytest.mark.asyncio
async def test_invalid_action_is_visible_to_browser(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/events/publish", json={"action": "ship"})
    assert response.status_code == 422
    assert "Unknown action: ship" in response.json()["detail"]
