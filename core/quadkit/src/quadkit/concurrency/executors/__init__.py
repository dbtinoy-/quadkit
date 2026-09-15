"""Task execution primitives: dispatcher, parallel execution, task manager."""

from __future__ import annotations

from quadkit.concurrency.executors.dispatcher import DispatcherImpl
from quadkit.concurrency.executors.task_manager import TaskManager

__all__ = ["DispatcherImpl", "TaskManager"]
