"""Convenience base class for admin contributor implementations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    AdminRouteSpec,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    SettingsPanelDefinition,
    WidgetParams,
)

if TYPE_CHECKING:
    from quadkit.contracts.admin.errors import AdminError
    from quadkit.contracts.admin.health_payload import HealthCheckPayload
    from quadkit.contracts.admin.types import WidgetViewModel
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.contracts.core.result import Result


class BaseAdminContributor:
    """Convenience base class for admin contributors.

    Provides no-op defaults for all ``AdminContributorProtocol`` methods.
    Subclasses override only the methods they need.
    """

    name: str = ""
    display_name: str = ""
    group: str = "framework"
    depends_on: tuple[str, ...] = ()
    icon: str = "box"
    priority: int = 100
    version: str = "0.0.0"
    package_source: str = "built-in"
    required_permissions: frozenset[str] = frozenset()

    @property
    def contributor_id(self) -> str:
        """Stable identifier for RBAC lookup — equals ``name``."""
        return self.name

    def get_resources(self) -> Sequence[type]:
        """Return an empty sequence by default."""
        return []

    def get_routes(self) -> Sequence[AdminRouteSpec]:
        """Return an empty sequence by default."""
        return []

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Return an empty list by default."""
        return []

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return an empty list by default."""
        return []

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return an empty list by default."""
        return []

    def get_settings_panels(self) -> Sequence[SettingsPanelDefinition]:
        """Return an empty list by default."""
        return []

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return an empty list by default."""
        return []

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        """Return an empty list by default."""
        return []

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """No-op boot hook."""

    async def on_admin_shutdown(self) -> None:
        """No-op shutdown hook."""

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        """Return a not-found error by default — override in subclasses."""
        from quadkit.contracts.admin.errors import WidgetNotFoundError
        from quadkit.contracts.core.result import Err

        result: Result[WidgetViewModel, AdminError] = cast(
            "Result[WidgetViewModel, AdminError]",
            Err(WidgetNotFoundError(self.name, widget_name)),
        )
        return result

    async def render_health_check(
        self,
        check_name: str,
    ) -> Result[HealthCheckPayload, AdminError]:
        """Default: this contributor does not serve the requested health check.

        Args:
            check_name: Name of the health check requested.

        Returns:
            ``Err(HealthCheckNotFoundError)`` — contributor does not provide this check.
        """
        from quadkit.contracts.admin.errors import HealthCheckNotFoundError
        from quadkit.contracts.core.result import Err

        result: Result[HealthCheckPayload, AdminError] = cast(
            "Result[HealthCheckPayload, AdminError]",
            Err(HealthCheckNotFoundError(self.name, check_name)),
        )
        return result


__all__ = ["BaseAdminContributor"]
