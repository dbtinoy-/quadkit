"""Management pages for quadkit-tasks admin."""

from __future__ import annotations

from quadkit.tasks.admin.pages.active import TasksActivePage
from quadkit.tasks.admin.pages.failed import TasksFailedPage
from quadkit.tasks.admin.pages.history import TasksHistoryPage
from quadkit.tasks.admin.pages.overview import TasksOverviewPage

__all__ = [
    "TasksActivePage",
    "TasksFailedPage",
    "TasksHistoryPage",
    "TasksOverviewPage",
]
