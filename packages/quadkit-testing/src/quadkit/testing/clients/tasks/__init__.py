"""Testing clients and test beds for quadkit-tasks."""

from __future__ import annotations

from quadkit.testing.clients.tasks.bed import TaskTestBed
from quadkit.testing.clients.tasks.client import TaskTestClient
from quadkit.testing.clients.tasks.data import TaskTestData
from quadkit.testing.clients.tasks.mocks import (
    MockTaskExecutor,
    MockTaskQueue,
    MockTaskResult,
    MockTasksProvider,
)

__all__ = [
    "MockTaskExecutor",
    "MockTaskQueue",
    "MockTaskResult",
    "MockTasksProvider",
    "TaskTestBed",
    "TaskTestClient",
    "TaskTestData",
]
