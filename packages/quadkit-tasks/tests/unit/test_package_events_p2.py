"""P2 guardrail: quadkit-tasks must expose a canonical root events module."""

from __future__ import annotations


def test_tasks_events_root_module_exists() -> None:
    from quadkit.tasks.events import TaskCompletedEvent, TaskFailedEvent, TaskQueuedEvent

    assert TaskQueuedEvent.__name__ == "TaskQueuedEvent"
    assert TaskCompletedEvent.__name__ == "TaskCompletedEvent"
    assert TaskFailedEvent.__name__ == "TaskFailedEvent"


def test_tasks_events_re_exported_from_package_root() -> None:
    import quadkit.tasks as tasks_pkg

    assert hasattr(tasks_pkg, "TaskQueuedEvent")
    assert hasattr(tasks_pkg, "TaskCompletedEvent")
    assert hasattr(tasks_pkg, "TaskFailedEvent")
