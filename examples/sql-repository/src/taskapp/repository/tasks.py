"""SQLite-backed task repository using Quadkit's database protocol."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


class TaskRepository:
    """Small repository that keeps SQL details out of the controller."""

    def __init__(self, database: DatabaseProviderProtocol) -> None:
        self._database = database

    async def initialize(self, seed: list[dict[str, Any]]) -> None:
        """Create the demo table and seed it once."""
        await self._database.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'todo',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        count = await self._database.execute_query(
            "SELECT COUNT(*) AS count FROM tasks"
        )
        if count.rows[0]["count"] == 0:
            for task in seed:
                await self._database.execute_insert("tasks", task)

    async def list(self) -> list[dict[str, Any]]:
        """Return tasks ordered by priority, then newest ID."""
        result = await self._database.execute_query(
            "SELECT id, title, status, priority, created_at "
            "FROM tasks ORDER BY priority DESC, id DESC"
        )
        return result.rows

    async def get(self, task_id: int) -> dict[str, Any] | None:
        """Return one task by ID."""
        result = await self._database.execute_query(
            "SELECT id, title, status, priority, created_at FROM tasks WHERE id = ?",
            [task_id],
        )
        return result.rows[0] if result.rows else None

    async def create(self, title: str, priority: int = 0) -> dict[str, Any]:
        """Insert a task and return the stored row."""
        result = await self._database.execute_insert(
            "tasks",
            {"title": title, "status": "todo", "priority": priority},
        )
        created = await self.get(int(result.inserted_id))
        if created is None:
            raise RuntimeError("inserted task could not be read back")
        return created

    async def update_status(self, task_id: int, status: str) -> dict[str, Any] | None:
        """Update a task status and return the stored row."""
        result = await self._database.execute_update(
            "tasks",
            {"status": status},
            "id = ?",
            [task_id],
        )
        return await self.get(task_id) if result.affected_rows else None

    async def delete(self, task_id: int) -> bool:
        """Delete a task and report whether a row was affected."""
        result = await self._database.execute_delete("tasks", "id = ?", [task_id])
        return bool(result.affected_rows)

    async def stats(self) -> dict[str, int]:
        """Return counts useful to the browser console."""
        result = await self._database.execute_query(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done "
            "FROM tasks"
        )
        row = result.rows[0]
        return {"total": int(row["total"]), "done": int(row["done"] or 0)}
