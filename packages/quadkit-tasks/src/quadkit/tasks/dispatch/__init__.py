"""Function-centric background dispatch via ``.delay()``.

Provides the :func:`delay` decorator, which wraps any async function and adds
a ``.delay()`` method for safe fire-and-forget background dispatch.  All
spawned tasks are tracked in a module-level set so CPython's garbage collector
cannot reclaim them before they finish — the canonical prevention for the
"task vanishes" bug (Ruff RUF006).

This is **not** a replacement for the full task-queue system (``@task`` +
``TaskProvider``).  Use ``.delay()`` for lightweight in-process background
work (sending a notification, flushing a local buffer, emitting an audit log)
where queue persistence, retries, and distributed workers are unnecessary.

Example:
    ```python
    from quadkit.tasks.dispatch import delay

    @delay
    async def send_export_email(user_id: str, file_path: str) -> None:
        await mailer.send(user_id, attachment=file_path)

    # Schedules the coroutine as a background asyncio task; returns the Task.
    task = send_export_email.delay(user_id="u-1", file_path="/exports/jan.csv")
    ```

The decorated function remains fully callable as a normal coroutine function:
    ```python
    await send_export_email(user_id="u-1", file_path="/exports/jan.csv")
    ```
"""

from __future__ import annotations

from quadkit.tasks.dispatch.core import _background_tasks, _DelayedCallable, delay

__all__ = ["_DelayedCallable", "_background_tasks", "delay"]
