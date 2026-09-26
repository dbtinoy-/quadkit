"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Task Console demo.

This is a single-package niche demo: ``TasksModule`` owns the entire
background-processing stack (``TaskProviderProtocol``, worker pool,
scheduler, result store, dead letter queue) — every object the browser
touches is ``quadkit-tasks`` behavior, not a look-alike. The application
layer only presents that package-owned API in a small task console: enqueue
a job, poll for its result, watch worker/scheduler stats, and retry
dead-lettered jobs.
"""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.module import TasksModule
from quadkit.web.module import WebModule
from task_console.controllers.api import TaskConsoleApiController
from task_console.di.provider import TaskConsoleProvider
from task_console.ui.pages import TaskConsolePageController


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the task console demo.

    ``TasksModule.configure()`` is given an explicit ``MemoryTaskQueue()``
    (its own default when ``queue=None``) so the demo stays dependency-free
    — a single worker with the real scheduler enabled processes every job
    the console enqueues.
    """
    return [
        TasksModule.configure(
            queue=MemoryTaskQueue(),
            worker_count=1,
            enable_scheduler=True,
        ),
        WebModule.configure(
            controllers=[
                TaskConsoleApiController,
                TaskConsolePageController,
            ],
        ),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the task console demo."""
    return [TaskConsoleProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the task console application."""
    app = Application(name="task-console", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
