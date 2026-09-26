"""SQL admin contributor — provides widget and health data for quadkit-sql."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from quadkit.contracts import Result
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
from quadkit.result import Err, Ok

if TYPE_CHECKING:
    from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)

_WIDGETS: tuple[DashboardWidgetDefinition, ...] = (
    DashboardWidgetDefinition(
        name="pool_utilization",
        title="DB Pool",
        contributor="sql",
        render_endpoint="/admin/sql/widgets/pool_utilization",
        size=WidgetSize.MEDIUM,
        category=WidgetCategory.HEALTH,
        view_kind=WidgetKind.STAT,
        refresh_interval_seconds=15,
        order=10,
        description="Current connection pool utilization as a percentage.",
    ),
    DashboardWidgetDefinition(
        name="query_stats",
        title="Query Stats",
        contributor="sql",
        render_endpoint="/admin/sql/widgets/query_stats",
        size=WidgetSize.MEDIUM,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        refresh_interval_seconds=30,
        order=20,
        description="Aggregate query counts, latency, and slow-query count.",
    ),
    DashboardWidgetDefinition(
        name="migration_status",
        title="Migrations",
        contributor="sql",
        render_endpoint="/admin/sql/widgets/migration_status",
        size=WidgetSize.SMALL,
        category=WidgetCategory.RESOURCES,
        view_kind=WidgetKind.HEALTH,
        refresh_interval_seconds=300,
        order=30,
        description="Number of pending Alembic migrations.",
    ),
)

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="Database",
        url="/admin/sql",
        icon="database",
        group="infrastructure",
        order=15,
        children=(
            NavigationContribution(
                label="Migrations",
                url="/admin/sql/migrations",
                icon="arrow-up-circle",
                group="infrastructure",
                order=10,
            ),
            NavigationContribution(
                label="Queries",
                url="/admin/sql/queries",
                icon="search",
                group="infrastructure",
                order=20,
            ),
        ),
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="sql_connectivity",
        contributor="sql",
        component="database",
        check_endpoint="/admin/sql/health/connectivity",
        icon="database",
        description="Verifies the primary database connection is reachable.",
    ),
)

_ACTIONS: tuple[AdminActionDefinition, ...] = (
    AdminActionDefinition(
        name="run_migrations",
        title="Run Pending Migrations",
        contributor="sql",
        handler="quadkit.sql.admin.actions:run_migrations",
        icon="arrow-up-circle",
        category="operations",
    ),
)


class SqlAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-sql package.

    Provides 3 widgets: pool utilization, query stats, and migration status.
    Each widget is handled by a dedicated handler class that returns
    structured WidgetContent directly. Dependencies are resolved from the
    container in ``on_admin_boot``.
    """

    name = "sql"
    display_name = "Database"
    group = "infrastructure"
    icon = "database"
    priority = 15

    def __init__(self) -> None:
        self._handlers: dict[str, WidgetHandlerProtocol] | None = None

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve widget handler dependencies from the DI container.

        Args:
            container: The DI container resolver.
        """
        from quadkit.sql.admin.handlers.migration_status import (
            MigrationStatusWidgetHandler,
        )
        from quadkit.sql.admin.handlers.pool_utilization import (
            PoolUtilizationWidgetHandler,
        )
        from quadkit.sql.admin.handlers.query_stats import QueryStatsWidgetHandler

        pool_handler = await container.resolve(PoolUtilizationWidgetHandler)
        query_handler = await container.resolve(QueryStatsWidgetHandler)
        migration_handler = await container.resolve(MigrationStatusWidgetHandler)
        self._handlers = {
            "pool_utilization": pool_handler,
            "query_stats": query_handler,
            "migration_status": migration_handler,
        }

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Return dashboard widget definitions.

        Returns:
            Sequence of DashboardWidgetDefinition instances.
        """
        return list(_WIDGETS)

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return navigation contributions.

        Returns:
            Sequence of NavigationContribution instances.
        """
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return health check definitions.

        Returns:
            Sequence of AdminHealthDefinition instances.
        """
        return list(_HEALTH_DEFS)

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        """Return admin action definitions.

        Returns:
            Sequence of AdminActionDefinition instances.
        """
        return list(_ACTIONS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return management page definitions.

        Returns:
            Sequence of ManagementPageDefinition instances.
        """
        return [
            ManagementPageDefinition(
                name="sql_overview",
                title="Database Overview",
                contributor="sql",
                route_path="/sql",
                handler="quadkit.sql.admin.pages.overview:SqlOverviewPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="database",
                description="Database connection status and migration count",
                order=10,
            ),
            ManagementPageDefinition(
                name="sql_migrations",
                title="Database Migrations",
                contributor="sql",
                route_path="/sql/migrations",
                handler="quadkit.sql.admin.pages.migrations:SqlMigrationsPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="arrow-up-circle",
                description="View applied database migrations",
                order=20,
            ),
            ManagementPageDefinition(
                name="sql_queries",
                title="Database Queries",
                contributor="sql",
                route_path="/sql/queries",
                handler="quadkit.sql.admin.pages.queries:SqlQueriesPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="search",
                description="Recent database queries and performance",
                order=30,
            ),
        ]

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        """Render a widget by name using registry dispatch.

        Registry dispatch — no if/elif. Infrastructure exceptions propagate.

        Args:
            widget_name: Name of the widget to render.
            params: Widget parameters.

        Returns:
            Result containing a WidgetViewModel with structured content,
            or WidgetNotFoundError if the widget is not registered.
        """
        if self._handlers is None:
            return cast(
                "Result[WidgetViewModel, AdminError]",
                Err(AdminError("SqlAdminContributor not booted")),
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


__all__ = ["SqlAdminContributor"]
