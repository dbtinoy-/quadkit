"""P2 hook surface import verification for quadkit-tasks."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_tasks_hooks_root_module_exists() -> None:
    """Expose the task hook payloads from both direct and package-root imports."""
    import quadkit.tasks
    from quadkit.tasks.hooks import (
        TaskCompletedHook,
        TaskEnqueuedHook,
        TaskFailedHook,
        TaskStartedHook,
    )

    assert TaskEnqueuedHook.__name__ == "TaskEnqueuedHook"
    assert TaskStartedHook.__name__ == "TaskStartedHook"
    assert TaskCompletedHook.__name__ == "TaskCompletedHook"
    assert TaskFailedHook.__name__ == "TaskFailedHook"
    assert quadkit.tasks.TaskEnqueuedHook is TaskEnqueuedHook
    assert quadkit.tasks.TaskStartedHook is TaskStartedHook
    assert quadkit.tasks.TaskCompletedHook is TaskCompletedHook
    assert quadkit.tasks.TaskFailedHook is TaskFailedHook


def test_tasks_hook_payloads_are_frozen_and_keyword_only() -> None:
    """Keep task hook payloads frozen and keyword-only like the accepted web seed."""
    from quadkit.tasks.hooks import TaskEnqueuedHook, TaskFailedHook

    enqueued = TaskEnqueuedHook(task_name="send_email", queue_name="default")
    failed = TaskFailedHook(
        task_name="send_email", task_id="t1", reason="SMTP unavailable"
    )

    assert is_dataclass(enqueued)
    assert is_dataclass(failed)

    with pytest.raises(TypeError):
        TaskEnqueuedHook("send_email", "default")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        enqueued.task_name = "other"  # type: ignore[misc]
