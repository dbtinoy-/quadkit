"""Admin contributor for quadkit-tasks — surfaces task summary and duration
widgets into the Quadkit admin dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.errors import AdminError, WidgetNotFoundError
from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
    WidgetCategory,
    WidgetKind,
    WidgetParams,
    WidgetSize,
    WidgetViewModel,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
    from quadkit.contracts.core.di import ContainerResolverProtocol

_WIDGETS: tuple[DashboardWidgetDefinition, ...] = (
    DashboardWidgetDefinition(
        name="tasks_summary",
        title="Tasks Summary",
        contributor="tasks",
        render_endpoint="/admin/tasks/widgets/tasks_summary",
        size=WidgetSize.LARGE,
        category=WidgetCategory.ACTIVITY,
        view_kind=WidgetKind.STAT,
        description="Overview of queued, running, and failed tasks.",
    ),
    DashboardWidgetDefinition(
        name="avg_duration",
        title="Avg Task Duration",
        contributor="tasks",
        render_endpoint="/admin/tasks/widgets/avg_duration",
        size=WidgetSize.SMALL,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="Average task execution duration over the last hour.",
    ),
)

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="Tasks",
        url="/admin/tasks",
        icon="check-circle",
        group="infrastructure",
        order=40,
        children=(
            NavigationContribution(
                label="Active",
                url="/admin/tasks/active",
                icon="play-circle",
                group="infrastructure",
                order=10,
            ),
            NavigationContribution(
                label="History",
                url="/admin/tasks/history",
                icon="clock",
                group="infrastructure",
                order=20,
            ),
            NavigationContribution(
                label="Failed",
                url="/admin/tasks/failed",
                icon="x-circle",
                group="infrastructure",
                order=30,
            ),
        ),
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="tasks.worker",
        contributor="tasks",
        component="Task Worker",
        check_endpoint="/admin/tasks/health/worker",
        description="Verifies at least one task worker is running and healthy.",
    ),
)

_ACTIONS: tuple[AdminActionDefinition, ...] = (
    AdminActionDefinition(
        name="retry_failed_tasks",
        title="Retry All Failed Tasks",
        contributor="tasks",
        handler="quadkit.tasks.admin.actions:retry_failed_tasks",
        icon="refresh-cw",
        category="operations",
    ),
)


class TasksAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-tasks package."""

    name = "tasks"
    display_name = "Tasks"
    group = "infrastructure"
    icon = "check-circle"
    priority = 40

    def __init__(self) -> None:
        self._handlers: dict[str, WidgetHandlerProtocol] | None = None

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve widget handler dependencies from the DI container.

        Args:
            container: The DI container resolver.
        """
        self._handlers = {
            "tasks_summary": await container.resolve(TasksSummaryWidgetHandler),
            "avg_duration": await container.resolve(AvgDurationWidgetHandler),
        }

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Return dashboard widget definitions.

        Returns:
            Sequence of DashboardWidgetDefinition for tasks widgets.
        """
        return list(_WIDGETS)

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return navigation items.

        Returns:
            Sequence of NavigationContribution for tasks navigation.
        """
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return health check definitions.

        Returns:
            Sequence of AdminHealthDefinition for tasks health checks.
        """
        return list(_HEALTH_DEFS)

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        """Return admin action definitions.

        Returns:
            Sequence of AdminActionDefinition for tasks actions.
        """
        return list(_ACTIONS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return management page definitions.

        Returns:
            Sequence of ManagementPageDefinition for tasks management pages.
        """
        return [
            ManagementPageDefinition(
                name="tasks_overview",
                title="Tasks Overview",
                contributor="tasks",
                route_path="/tasks",
                handler="quadkit.tasks.admin.pages.overview:TasksOverviewPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="check-circle",
                description="Task scheduler overview and metrics",
                order=10,
            ),
            ManagementPageDefinition(
                name="tasks_active",
                title="Active Tasks",
                contributor="tasks",
                route_path="/tasks/active",
                handler="quadkit.tasks.admin.pages.active:TasksActivePage",
                category=PageCategory.INFRASTRUCTURE,
                icon="play-circle",
                description="Currently running tasks",
                order=20,
            ),
            ManagementPageDefinition(
                name="tasks_history",
                title="Task History",
                contributor="tasks",
                route_path="/tasks/history",
                handler="quadkit.tasks.admin.pages.history:TasksHistoryPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="clock",
                description="Completed task history",
                order=30,
            ),
            ManagementPageDefinition(
                name="tasks_failed",
                title="Failed Tasks",
                contributor="tasks",
                route_path="/tasks/failed",
                handler="quadkit.tasks.admin.pages.failed:TasksFailedPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="x-circle",
                description="Failed tasks and error details",
                order=40,
            ),
        ]

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        """Render a widget by name using registry dispatch.

        Each widget handler returns structured WidgetContent directly;
        the contributor wraps it in a WidgetViewModel. Infrastructure
        exceptions propagate.

        Args:
            widget_name: Name of the widget to render.
            params: Typed widget parameters.

        Returns:
            Result containing a WidgetViewModel with structured content,
            or WidgetNotFoundError if the widget is not registered.
        """
        if self._handlers is None:
            return cast(
                "Result[WidgetViewModel, AdminError]",
                Err(AdminError("TasksAdminContributor not booted")),
            )
        handler = self._handlers.get(widget_name)
        if handler is None:
            return cast(
                "Result[WidgetViewModel, AdminError]",
                Err(WidgetNotFoundError(self.name, widget_name)),
            )
        result = await handler.get_data(params)
        if result.is_err():
            return cast("Result[WidgetViewModel, AdminError]", result)
        return cast(
            "Result[WidgetViewModel, AdminError]",
            Ok(WidgetViewModel(content=result.unwrap())),
        )


__all__ = ["TasksAdminContributor"]
