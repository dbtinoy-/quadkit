"""Offline seed rows for the SQL repository demo."""

from __future__ import annotations

SEED_TASKS: list[dict[str, object]] = [
    {"title": "Read the generated schema", "status": "todo", "priority": 2},
    {"title": "Try the status update endpoint", "status": "in_progress", "priority": 1},
    {"title": "Inspect the SQL-backed task list", "status": "done", "priority": 0},
]

__all__ = ["SEED_TASKS"]
