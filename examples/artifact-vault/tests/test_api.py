"""Exercise BlobStoreProtocol through the browser API."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_seeded_artifact_has_metadata(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/artifacts")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["artifacts"][0]["path"] == "docs/welcome.txt"
    assert data["artifacts"][0]["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_upload_preview_access_and_delete(client: httpx.AsyncClient) -> None:
    uploaded = await client.post("/api/artifacts/upload", json={"name": "notes/demo.txt", "content": "hello vault", "content_type": "text/plain", "owner": "qa"})
    assert uploaded.json()["artifact"]["size"] == 11
    preview = await client.get("/api/artifacts/content/notes/demo.txt")
    assert preview.json()["content"] == "hello vault"
    access = await client.get("/api/artifacts/access/notes/demo.txt")
    assert access.json()["public_url"] == "memory://notes/demo.txt"
    assert access.json()["signed_access"] is False
    deleted = await client.delete("/api/artifacts/notes/demo.txt")
    assert deleted.json()["ok"] is True
    assert (await client.get("/api/artifacts")).json()["count"] == 1


@pytest.mark.asyncio
async def test_upload_rejects_unsafe_paths(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/artifacts/upload", json={"name": "../secret.txt", "content": "nope"})
    assert response.status_code == 422
    assert "detail" in response.json()
