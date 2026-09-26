"""Factory helpers for composing task workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.tasks.workflows.core import TaskChain, TaskStep


def chain(*steps: TaskStep, stop_on_error: bool = True) -> TaskChain:
    """Create a sequential :class:`TaskChain` from the given steps.

    Each step receives the output of the previous step as its input.

    Args:
        *steps: One or more :class:`TaskStep` instances to chain.
        stop_on_error: Whether to abort the pipeline on the first failure.
            Defaults to ``True``.

    Returns:
        A configured :class:`TaskChain` ready to ``await .execute()``.

    Example::

        result = await chain(
            TaskStep("validate", validate_input),
            TaskStep("process", process_data),
            TaskStep("persist", save_to_db),
        ).execute(raw_data)
    """
    from quadkit.tasks.workflows.core import TaskChain

    return TaskChain(list(steps), stop_on_error=stop_on_error)
