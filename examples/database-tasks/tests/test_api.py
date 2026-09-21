"""Exercise the real database-tasks composition root through HTTP."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from database_tasks.app import create_app
from quadkit.web import WebProvider


async def test_create_list_get_roundtrip(client: httpx.AsyncClient) -> None:
    created = await client.post("/tasks", json={"title": "write docs"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["done"] is False

    fetched = await client.get(f"/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "write docs"

    listing = await client.get("/tasks")
    assert [t["id"] for t in listing.json()["tasks"]] == [task_id]


async def test_blank_title_is_a_422_problem(client: httpx.AsyncClient) -> None:
    response = await client.post("/tasks", json={"title": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert "title" in body["detail"].lower()


async def test_unknown_task_is_a_404_problem(client: httpx.AsyncClient) -> None:
    response = await client.get("/tasks/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_complete_marks_done(client: httpx.AsyncClient) -> None:
    created = await client.post("/tasks", json={"title": "ship it"})
    task_id = created.json()["id"]
    done = await client.post(f"/tasks/{task_id}/complete")
    assert done.status_code == 200
    assert done.json()["done"] is True


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "database-tasks"
    assert isinstance(body["endpoints"], list) and body["endpoints"]


async def test_complete_marks_done_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh app over the same file sees the row — real persistence."""
    db = str(tmp_path / "tasks.db")
    monkeypatch.setenv("QK_DATABASE_TASKS__DB_PATH", db)

    application = create_app()
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=web.starlette), base_url="http://first"
        ) as first:
            task_id = (await first.post("/tasks", json={"title": "ship it"})).json()["id"]
            done = await first.post(f"/tasks/{task_id}/complete")
            assert done.json()["done"] is True
    finally:
        await application.stop()

    application2 = create_app()
    await application2.start()
    try:
        web2 = await application2.container.resolve(WebProvider)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=web2.starlette), base_url="http://second"
        ) as second:
            fetched = await second.get(f"/tasks/{task_id}")
            assert fetched.status_code == 200
            assert fetched.json()["done"] is True
    finally:
        await application2.stop()


async def test_boot_fails_fast_on_unwritable_database_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure injection: an unusable DB path surfaces at boot with the
    path in the error, not as a 500 on the first request."""
    monkeypatch.setenv("QK_DATABASE_TASKS__DB_PATH", "/nonexistent-dir/tasks.db")
    application = create_app()
    with pytest.raises(Exception, match="unable to open|readonly"):
        await application.start()
