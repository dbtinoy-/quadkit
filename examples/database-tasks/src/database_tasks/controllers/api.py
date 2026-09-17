"""Convention followed: **Controller pattern** — stateless HTTP adapters;
expected failures are ``Err(domain error)`` values rendered as RFC-9457
``ProblemDetail`` by the Result bridge (``ValidationError`` → 422 and
``NotFoundError`` → 404 are built-in mappings; no registration needed).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions import NotFoundError, ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from database_tasks.services.repository import TaskRepository


class TasksController(Controller):
    """CRUD over the task table; all storage calls run off the event loop."""

    prefix = "/"

    def __init__(self, repo: TaskRepository | None = None) -> None:
        self._repo = repo

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "database-tasks",
            "summary": "SQLite CRUD through a repository service.",
            "endpoints": [
                "POST /tasks",
                "GET /tasks",
                "GET /tasks/{task_id}",
                "POST /tasks/{task_id}/complete",
            ],
        }

    @post("/tasks", status_code=201)
    async def create(
        self, payload: dict = body()
    ) -> Result[dict[str, Any], ValidationError]:
        """Create a task; a blank title is a 422 problem, not a 500."""
        title = str(payload.get("title", "")).strip()
        if not title:
            return Err(ValidationError("title is required"))
        return Ok(await asyncio.to_thread(self._repo.create, title))

    @get("/tasks")
    async def list_all(self) -> dict[str, Any]:
        """Return every task, oldest first."""
        return {"tasks": await asyncio.to_thread(self._repo.list)}

    @get("/tasks/{task_id}")
    async def get_one(self, task_id: int) -> Result[dict[str, Any], NotFoundError]:
        """Return one task; an unknown id is a 404 problem."""
        task = await asyncio.to_thread(self._repo.get, task_id)
        if task is None:
            return Err(NotFoundError("task not found"))
        return Ok(task)

    @post("/tasks/{task_id}/complete")
    async def complete(self, task_id: int) -> Result[dict[str, Any], NotFoundError]:
        """Mark one task done; an unknown id is a 404 problem."""
        task = await asyncio.to_thread(self._repo.complete, task_id)
        if task is None:
            return Err(NotFoundError("task not found"))
        return Ok(task)


__all__ = ["TasksController"]
