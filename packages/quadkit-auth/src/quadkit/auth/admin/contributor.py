"""Admin contributor for quadkit-auth — surfaces session, token, and login
widgets into the Quadkit admin dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

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
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.logging import get_logger
from quadkit.result import Err, Ok

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)

_WIDGETS: tuple[DashboardWidgetDefinition, ...] = (
    DashboardWidgetDefinition(
        name="active_sessions",
        title="Active Sessions",
        contributor="auth",
        render_endpoint="/admin/auth/widgets/active_sessions",
        size=WidgetSize.LARGE,
        category=WidgetCategory.ACTIVITY,
        view_kind=WidgetKind.STAT,
        description="Number of currently active authenticated sessions.",
    ),
    DashboardWidgetDefinition(
        name="token_refresh_rate",
        title="Token Refresh Rate",
        contributor="auth",
        render_endpoint="/admin/auth/widgets/token_refresh_rate",
        size=WidgetSize.SMALL,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="JWT / OAuth2 token refresh requests per minute.",
    ),
    DashboardWidgetDefinition(
        name="failed_logins",
        title="Failed Logins",
        contributor="auth",
        render_endpoint="/admin/auth/widgets/failed_logins",
        size=WidgetSize.SMALL,
        category=WidgetCategory.HEALTH,
        view_kind=WidgetKind.STAT,
        description="Count of failed login attempts over the last hour.",
    ),
)

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="Auth",
        url="/admin/auth",
        icon="lock-closed",
        group="security",
        order=25,
        children=(
            NavigationContribution(
                label="Users",
                url="/admin/auth/users",
                icon="users",
                group="security",
                order=10,
            ),
            NavigationContribution(
                label="Sessions",
                url="/admin/auth/sessions",
                icon="activity",
                group="security",
                order=20,
            ),
            NavigationContribution(
                label="Tokens",
                url="/admin/auth/tokens",
                icon="key",
                group="security",
                order=30,
            ),
        ),
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="auth.token_store",
        contributor="auth",
        component="Token Store",
        check_endpoint="/admin/auth/health/token_store",
        description="Verifies the token storage backend is available.",
    ),
)

_ACTIONS: tuple[AdminActionDefinition, ...] = (
    AdminActionDefinition(
        name="revoke_all_sessions",
        title="Revoke All Sessions",
        contributor="auth",
        handler="quadkit.auth.admin.actions:revoke_all_sessions",
        icon="shield-off",
        confirmation_message="This will immediately log out all active users. Are you sure?",
        destructive=True,
        category="security",
    ),
)


class AuthAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-auth package.

    Provides 3 widgets: active sessions, token refresh rate, and failed logins.
    Each widget is handled by a dedicated handler class that returns
    structured WidgetContent directly. Dependencies are resolved from the
    container in ``on_admin_boot``.
    """

    name = "auth"
    display_name = "Auth"
    group = "security"
    icon = "lock-closed"
    priority = 25

    def __init__(self) -> None:
        """Initialize the contributor with no arguments.

        All DI-dependent attributes are resolved in ``on_admin_boot``.
        """
        self._handlers: dict[str, WidgetHandlerProtocol] = {}

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve auth DI dependencies from the container.

        Args:
            container: The DI container resolver.
        """
        from quadkit.auth.admin.handlers.active_sessions import (
            ActiveSessionsWidgetHandler,
        )
        from quadkit.auth.admin.handlers.failed_logins import (
            FailedLoginsWidgetHandler,
        )
        from quadkit.auth.admin.handlers.token_refresh_rate import (
            TokenRefreshRateWidgetHandler,
        )

        try:
            self._handlers = {
                "active_sessions": await container.resolve(ActiveSessionsWidgetHandler),
                "token_refresh_rate": await container.resolve(
                    TokenRefreshRateWidgetHandler
                ),
                "failed_logins": await container.resolve(FailedLoginsWidgetHandler),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("auth_contributor.handlers_unavailable", error=str(exc))

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Return the dashboard widget definitions for this contributor."""
        return list(_WIDGETS)

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return the navigation items for this contributor."""
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return the health check definitions for this contributor."""
        return list(_HEALTH_DEFS)

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        """Return the action definitions for this contributor."""
        return list(_ACTIONS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return the management page definitions for this contributor."""
        return [
            ManagementPageDefinition(
                name="auth_overview",
                title="Auth Overview",
                contributor=self.name,
                route_path="/auth",
                handler="quadkit.auth.admin.pages.overview:AuthOverviewPage",
                icon="lock-closed",
                category=PageCategory.SECURITY,
            ),
            ManagementPageDefinition(
                name="auth_users",
                title="Auth Users",
                contributor=self.name,
                route_path="/auth/users",
                handler="quadkit.auth.admin.pages.users:AuthUsersPage",
                icon="users",
                category=PageCategory.SECURITY,
            ),
            ManagementPageDefinition(
                name="auth_sessions",
                title="Auth Sessions",
                contributor=self.name,
                route_path="/auth/sessions",
                handler="quadkit.auth.admin.pages.sessions:AuthSessionsPage",
                icon="activity",
                category=PageCategory.SECURITY,
            ),
            ManagementPageDefinition(
                name="auth_tokens",
                title="Auth Tokens",
                contributor=self.name,
                route_path="/auth/tokens",
                handler="quadkit.auth.admin.pages.tokens:AuthTokensPage",
                icon="key",
                category=PageCategory.SECURITY,
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
        handler: Any = self._handlers.get(widget_name)
        if handler is None:
            return Err(cast("AdminError", WidgetNotFoundError(self.name, widget_name)))

        result = await handler.get_data(params)
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok(WidgetViewModel(content=result.unwrap()))


__all__ = ["AuthAdminContributor"]
