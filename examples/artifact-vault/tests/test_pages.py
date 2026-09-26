"""Browser surface smoke tests."""

from __future__ import annotations

import httpx


async def test_console_explains_storage_flow(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Artifact Vault" in response.text
    assert "Upload an artifact" in response.text
    assert 'type="file"' in response.text
    assert "BlobStoreProtocol" in response.text


async def test_static_assets(client: httpx.AsyncClient) -> None:
    assert (await client.get("/static/style.css")).status_code == 200
    assert (await client.get("/static/app.js")).status_code == 200
