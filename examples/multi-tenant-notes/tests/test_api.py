"""Exercise the real multi-tenant-notes composition root through HTTP —
isolation is the behaviour under test."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette

from multi_tenant_notes.app import create_app
from quadkit.web import WebProvider

ACME = {"X-Tenant-Id": "acme"}
GLOBEEX = {"X-Tenant-Id": "globex"}


async def _boot() -> AsyncIterator[tuple[Starlette, httpx.AsyncClient]]:
    application = create_app()
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=web.starlette), base_url="http://test"
        )
        yield web.starlette, client
        await client.aclose()
    finally:
        await application.stop()


async def test_tenants_are_isolated(client: httpx.AsyncClient) -> None:
    created = await client.post("/notes", json={"text": "acme secret"}, headers=ACME)
    assert created.status_code == 201

    acme_list = await client.get("/notes", headers=ACME)
    assert [n["text"] for n in acme_list.json()["notes"]] == ["acme secret"]

    globex_list = await client.get("/notes", headers=GLOBEEX)
    assert globex_list.json()["notes"] == []

    # Cross-tenant id fetch is a 404, not a leak.
    note_id = created.json()["id"]
    response = await client.get(f"/notes/{note_id}", headers=GLOBEEX)
    assert response.status_code == 404


async def test_missing_tenant_header_is_rejected(client: httpx.AsyncClient) -> None:
    listing = await client.get("/notes")
    assert listing.status_code == 400
    assert "x-tenant-id" in listing.json()["detail"].lower()

    created = await client.post("/notes", json={"text": "hi"})
    assert created.status_code == 400


async def test_tenant_cap_is_a_409_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The typed-config cap (default: unlimited) refuses politely when set."""
    monkeypatch.setenv("QK_MULTI_TENANT_NOTES__MAX_NOTES_PER_TENANT", "1")
    async for _starlette, capped in _boot():
        first = await capped.post("/notes", json={"text": "one"}, headers=ACME)
        assert first.status_code == 201
        second = await capped.post("/notes", json={"text": "two"}, headers=ACME)
        assert second.status_code == 409
        assert "cap" in second.json()["detail"].lower()


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "multi-tenant-notes"
    assert isinstance(body["endpoints"], list) and body["endpoints"]
