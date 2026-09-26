"""HTTP tests for the SQL-backed task repository demo."""

from __future__ import annotations

import httpx
import pytest


class TestTasksAPI:
    """Exercise repository CRUD through the real application composition root."""

    @pytest.mark.asyncio
    async def test_list_tasks_reads_seed_rows(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/tasks/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
        assert {"id", "title", "status", "priority", "created_at"} <= set(data[0])

    @pytest.mark.asyncio
    async def test_create_task(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/api/tasks/tasks",
            json={"title": "Use parameterized SQL", "priority": 3},
        )
        assert response.status_code == 200
        task = response.json()["task"]
        assert task["title"] == "Use parameterized SQL"
        assert task["priority"] == 3
        assert task["status"] == "todo"

    @pytest.mark.asyncio
    async def test_create_task_validation(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/tasks/tasks", json={"title": ""})
        assert response.status_code == 422
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_update_task_status(self, client: httpx.AsyncClient) -> None:
        response = await client.put(
            "/api/tasks/tasks/1/status",
            json={"status": "done"},
        )
        assert response.status_code == 200
        assert response.json()["task"]["status"] == "done"

    @pytest.mark.asyncio
    async def test_update_task_status_invalid(self, client: httpx.AsyncClient) -> None:
        response = await client.put(
            "/api/tasks/tasks/1/status",
            json={"status": "blocked"},
        )
        assert response.status_code == 422
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_delete_task(self, client: httpx.AsyncClient) -> None:
        response = await client.delete("/api/tasks/tasks/3")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        missing = await client.get("/api/tasks/tasks/3")
        assert missing.status_code == 404
        assert "detail" in missing.json()

    @pytest.mark.asyncio
    async def test_stats(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/tasks/stats")
        assert response.status_code == 200
        assert {"total", "done"} <= set(response.json())
