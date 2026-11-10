"""Exercise state transitions and ApprovalChain through the web surface."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_request_moves_through_both_gates(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/workflow")).json()["state"] == "draft"
    submitted = await client.post("/api/workflow/transition", json={"event": "submit", "actor": "Maya"})
    assert submitted.json()["state"] == "manager_review"
    manager = await client.post("/api/workflow/transition", json={"event": "approve_manager", "actor": "Alex"})
    assert manager.json()["state"] == "finance_review"
    finance = await client.post("/api/workflow/transition", json={"event": "approve_finance", "actor": "Sam"})
    assert finance.json()["state"] == "approved"
    assert len(finance.json()["history"]) == 3


@pytest.mark.asyncio
async def test_reject_and_retry_are_visible(client: httpx.AsyncClient) -> None:
    await client.post("/api/workflow/transition", json={"event": "submit"})
    await client.post("/api/workflow/transition", json={"event": "reject_manager"})
    retry = await client.post("/api/workflow/retry", json={"actor": "Maya"})
    assert retry.json()["state"] == "manager_review"
    assert retry.json()["history"][-1]["event"] == "retry"


@pytest.mark.asyncio
async def test_approval_chain_preview(client: httpx.AsyncClient) -> None:
    rejected = await client.post("/api/workflow/policy", json={"manager_approved": True, "finance_approved": False})
    assert rejected.json() == {"approved": False, "policy": "all", "steps": {"manager": "approved", "finance": "rejected"}}
    approved = await client.post("/api/workflow/policy", json={})
    assert approved.json()["approved"] is True


@pytest.mark.asyncio
async def test_invalid_event_does_not_change_state(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/workflow/transition", json={"event": "approve_finance"})
    assert response.status_code == 409
    assert "detail" in response.json()
    assert (await client.get("/api/workflow")).json()["version"] == 0
