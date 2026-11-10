"""Exercise the real ``quadkit-ai-mcp`` server composition root over ASGI."""

from __future__ import annotations

import httpx


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "mcp-server"
    assert "GET /mcp/capabilities" in body["endpoints"]


async def test_capabilities_lists_tools_resources_and_prompts(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/mcp/capabilities")
    assert response.status_code == 200
    body = response.json()
    tool_names = {tool["name"] for tool in body["tools"]}
    assert {"lookup_incident", "list_incidents"} <= tool_names
    prompt_names = {prompt["name"] for prompt in body["prompts"]}
    assert "triage_incident" in prompt_names


async def test_call_tool_executes_registered_mcp_tool(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/mcp/tools/lookup_incident",
        json={"incident_id": "INC-101"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "lookup_incident"
    assert body["result"]["isError"] is False


async def test_unknown_tool_returns_problem_detail(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/mcp/tools/does_not_exist", json={})
    assert response.status_code == 404


async def test_raw_jsonrpc_reads_resource_and_prompt(
    client: httpx.AsyncClient,
) -> None:
    res = await client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/read",
            "params": {"uri": "runbook://payments"},
        },
    )
    assert res.status_code == 200
    assert res.json()["id"] == 10
    assert "result" in res.json()

    prompt_res = await client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "prompts/get",
            "params": {
                "name": "triage_incident",
                "arguments": {"incident_id": "INC-101"},
            },
        },
    )
    assert prompt_res.status_code == 200
    assert prompt_res.json()["id"] == 11
    assert "result" in prompt_res.json()
