"""Public registration of the tasks admin widget handlers.

``TasksAdminContributor`` resolves its widget handlers from the DI container in
``on_admin_boot``. Like the SQL contributor it is discovered through the
``the optional provider module`` entry-point group, so it mounts whenever
``quadkit-tasks`` is installed — including in applications that wire their own
task queue rather than using
:class:`~quadkit.tasks.di.provider.TaskProvider`. Those applications must
register the handlers too, or the contributor boots into an
``UnresolvableDependencyError`` and the Tasks widgets render nothing.

This module owns that registration: :class:`TaskProvider` delegates to it, and
applications with their own queue call it directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover — typing only
    from quadkit.contracts.core.di import ContainerRegistrarProtocol

logger = get_logger(__name__)


def register_admin_widget_handlers(
    container: ContainerRegistrarProtocol,
    *,
    queue: Any = None,
    worker_pool: Any = None,
) -> None:
    """Register the tasks admin widget handlers in the container.

    Args:
        container: DI registrar to bind the handlers into.
        queue: Task queue exposing ``get_task_count()``. ``None`` renders the
            pending cell as ``0`` instead of failing.
        worker_pool: Worker pool exposing ``get_pool_stats()``. ``None``
            renders the running/completed/failed cells as ``0``.
    """
    from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
    from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler

    container.transient(
        TasksSummaryWidgetHandler,
        factory=lambda: TasksSummaryWidgetHandler(
            queue_provider=queue, pool_provider=worker_pool
        ),
    )
    container.transient(
        AvgDurationWidgetHandler,
        factory=lambda: AvgDurationWidgetHandler(pool_provider=worker_pool),
    )
    logger.info("tasks.admin_widgets_registered", queue=queue is not None)


__all__ = ["register_admin_widget_handlers"]
