"""SQL repository demo — one SQLite-backed task resource.

The public surface is intentionally small: a standalone application factory,
its typed demo config, and the lifecycle provider that initializes the
Quadkit database repository.
"""

from __future__ import annotations

from taskapp.app import create_app
from taskapp.config import TaskAppConfig
from taskapp.di.provider import TaskProvider

__all__ = [
    "TaskAppConfig",
    "TaskProvider",
    "create_app",
]
