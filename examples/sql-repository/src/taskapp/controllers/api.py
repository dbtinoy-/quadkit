"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

HTTP surface for the single-purpose SQL task repository demo — the
**Result-pattern showcase** for the storage layer.

Every mutating/reading handler returns ``Result`` instead of raising or
hand-rolling error responses; the web pipeline does the boring work:

- ``Ok(payload)``              → serialized as JSON (200)
- ``Err(ValidationError)``     → HTTP 422 ProblemDetail (framework default)
- ``Err(NotFoundError)``       → HTTP 404 ProblemDetail (framework default)
- ``Err(InvalidStatusError)``  → HTTP 422 ProblemDetail (registered below)

So handlers read like use-cases ("validate → delegate → wrap") and
error-to-HTTP mapping lives in exactly one place.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, delete, get, post, put
from quadkit.web.routing.result_bridge import ResultResponseMapper
from taskapp.errors import InvalidStatusError
from taskapp.repository.tasks import TaskRepository

# Domain error → HTTP status mappings (rendered as ProblemDetail bodies).
ResultResponseMapper.register(InvalidStatusError, 422)


class TasksApiController(Controller):
    """Expose repository CRUD without putting SQL in the controller.

    Handlers return the service/repository outcome as ``Result``; the
    pipeline renders ``Ok`` payloads and maps ``Err`` types to ProblemDetail
    responses using the registered status mappings above.
    """

    prefix = "/api/tasks"
    _valid_statuses = {"todo", "in_progress", "done"}

    def __init__(self, repository: TaskRepository | None = None) -> None:
        self._repository = repository

    @post("/tasks")
    async def create_task(
        self, body: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Insert a task through ``TaskRepository.create``.

        Validation failures return ``Err(ValidationError)`` → 422
        ProblemDetail instead of a 200 with an ``error`` key.
        """
        title = str(body.get("title", "")).strip()
        if not title:
            return Err(ValidationError("Task title is required"))
        try:
            priority = int(body.get("priority", 0))
        except (TypeError, ValueError):
            return Err(ValidationError("Priority must be an integer"))
        return Ok({"task": await self._repository.create(title, priority)})

    @get("/tasks")
    async def list_tasks(self) -> list[dict[str, Any]]:
        """List rows read from SQLite through the repository."""
        return await self._repository.list()

    @get("/tasks/{task_id}")
    async def get_task(self, task_id: int) -> Result[dict[str, Any], NotFoundError]:
        """Read one task by primary key; missing rows map to 404."""
        task = await self._repository.get(task_id)
        if task is None:
            return Err(NotFoundError(f"Task {task_id} not found"))
        return Ok({"task": task})

    @put("/tasks/{task_id}/status")
    async def update_task_status(
        self,
        task_id: int,
        body: dict[str, Any],
    ) -> Result[dict[str, Any], InvalidStatusError | NotFoundError]:
        """Update a status through a parameterized repository query."""
        status = body.get("status", "todo")
        if status not in self._valid_statuses:
            return Err(
                InvalidStatusError(
                    f"Invalid status: {status}. "
                    f"Must be one of: {sorted(self._valid_statuses)}"
                )
            )
        task = await self._repository.update_status(task_id, status)
        if task is None:
            return Err(NotFoundError(f"Task {task_id} not found"))
        return Ok({"task": task})

    @delete("/tasks/{task_id}")
    async def delete_task(self, task_id: int) -> Result[dict[str, Any], NotFoundError]:
        """Delete a task through the database provider; missing rows 404."""
        if not await self._repository.delete(task_id):
            return Err(NotFoundError(f"Task {task_id} not found"))
        return Ok({"deleted": True})

    @get("/stats")
    async def stats(self) -> dict[str, Any]:
        """Return aggregate data from SQL, not an in-memory fixture."""
        return await self._repository.stats()


__all__ = ["TasksApiController"]
