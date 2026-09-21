"""Convention followed: **Service pattern** — persistence behind a
repository class; the domain speaks dicts, the repository speaks SQL.
No HTTP knowledge lives here.

SQLite-backed task storage for the Database Tasks demo. The driver is
synchronous on purpose — handlers call it via ``asyncio.to_thread`` —
swap in aiosqlite/asyncpg and ``await`` directly when you move to a
server database.
"""

from __future__ import annotations

import sqlite3
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
);
"""


class TaskRepository:
    """Synchronous SQLite access; handlers call it via ``asyncio.to_thread``."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        """Close the underlying connection (provider shutdown calls this)."""
        self._conn.close()

    def health(self) -> bool:
        """Return ``True`` when the database answers a trivial query."""
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def create(self, title: str) -> dict[str, Any]:
        cursor = self._conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        self._conn.commit()
        return self.get(cursor.lastrowid)

    def get(self, task_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return (
            None
            if row is None
            else {"id": row["id"], "title": row["title"], "done": bool(row["done"])}
        )

    def list(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        ).fetchall()
        return [
            {"id": r["id"], "title": r["title"], "done": bool(r["done"])} for r in rows
        ]

    def complete(self, task_id: int) -> dict[str, Any] | None:
        self._conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self._conn.commit()
        return self.get(task_id)


__all__ = ["TaskRepository"]
