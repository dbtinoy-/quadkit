"""End-to-end scenario tests over the JSON API."""

from __future__ import annotations

import httpx


async def test_lists_three_tools(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/tools")

    assert response.status_code == 200
    names = {t["name"] for t in response.json()}
    assert names == {"lookup_order", "calculate_refund", "search_kb"}


async def test_happy_scenario_end_to_end(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/ask",
        json={"question": "Where is order A-100?", "scenario": "happy"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == (
        "Order A-100 shipped via FastShip, tracking FS123456789."
    )
    assert [c["tool_name"] for c in body["tool_calls"]] == ["lookup_order"]
    assert all(c["succeeded"] for c in body["tool_calls"])
    assert body["steps"][0]["thought"].startswith("I need")


async def test_multi_tool_scenario_ordered_calls(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/ask",
        json={
            "question": "Refund my monitor arm order A-102",
            "scenario": "multi_tool",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [c["tool_name"] for c in body["tool_calls"]] == [
        "lookup_order",
        "calculate_refund",
    ]
    assert body["answer"] == "You are eligible for a $37.25 half refund."


async def test_failure_scenario_degrades_without_raising(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/ask",
        json={"question": "Teleport my order", "scenario": "failure"},
    )

    assert response.status_code == 200
    record = response.json()["tool_calls"][0]
    assert record["tool_name"] == "teleport_order"
    assert record["succeeded"] is False
    assert "Unknown tool" in record["error"]


async def test_unknown_scenario_is_404(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/ask",
        json={"question": "hi", "scenario": "nope"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "unknown scenario" in body["detail"].lower()


async def test_blank_question_is_422(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/ask",
        json={"question": "   ", "scenario": "happy"},
    )

    assert response.status_code == 422


async def test_runs_are_byte_stable(client: httpx.AsyncClient) -> None:
    payload = {"question": "q", "scenario": "happy"}
    first = (await client.post("/api/ask", json=payload)).json()
    second = (await client.post("/api/ask", json=payload)).json()

    del first["duration_ms"], second["duration_ms"]  # timing varies
    assert first == second
