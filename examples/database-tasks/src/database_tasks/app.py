"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Database Tasks demo: SQLite CRUD behind a
repository, async handlers via ``asyncio.to_thread``.
"""

from __future__ import annotations

from database_tasks.controllers.api import TasksController
from database_tasks.di.provider import DatabaseTasksProvider
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the Database Tasks demo."""
    return [WebModule.configure(controllers=[TasksController])]


def build_providers() -> list[Provider]:
    """Build the DI providers for the Database Tasks demo."""
    return [DatabaseTasksProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the Database Tasks application."""
    app = Application(name="database-tasks", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
