"""Admin contract protocols — service boundaries for the admin contributor system."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.admin.errors import AdminError
    from quadkit.contracts.admin.health_payload import HealthCheckPayload
    from quadkit.contracts.admin.types import (
        AdminActionDefinition,
        AdminHealthDefinition,
        AdminRouteSpec,
        DashboardWidgetDefinition,
        ManagementPageDefinition,
        NavigationContribution,
        SettingsPanelDefinition,
        WidgetParams,
        WidgetViewModel,
    )
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.contracts.core.result import Result


@runtime_checkable
class AdminContributorProtocol(Protocol):
    """Contract for packages that contribute admin dashboard surfaces.

    Any quadkit extension package can implement this protocol and register
    it via the ``the optional provider module`` entry point.  The admin
    dashboard discovers contributors at boot and assembles their widgets,
    pages, navigation, and actions into the unified admin UI.
    """

    @property
    def name(self) -> str:
        """Unique contributor identifier (e.g. 'cache', 'events', 'ai')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable contributor name for the admin UI."""
        ...

    @property
    def group(self) -> str:
        """Navigation group this contributor belongs to."""
        ...

    @property
    def icon(self) -> str:
        """Lucide icon name for the contributor."""
        ...

    @property
    def depends_on(self) -> tuple[str, ...]:
        """Contributor names that must boot before this contributor."""
        ...

    @property
    def priority(self) -> int:
        """Ordering priority within its group (lower = first)."""
        ...

    @property
    def version(self) -> str:
        """Semantic version of this contributor (e.g. '1.2.3')."""
        ...

    @property
    def package_source(self) -> str:
        """Python package name that provides this contributor (e.g. 'the optional provider')."""
        ...

    @property
    def contributor_id(self) -> str:
        """Stable unique identifier used for lookup and RBAC keying (equals ``name``)."""
        ...

    @property
    def required_permissions(self) -> frozenset[str]:
        """Permissions a user must hold to execute any action on this contributor."""
        ...

    def get_resources(self) -> Sequence[type]:
        """Return resource classes managed by this contributor."""
        ...

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Return widget definitions for the main dashboard."""
        ...

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return navigation entries for the admin sidebar."""
        ...

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return full management page definitions."""
        ...

    def get_settings_panels(self) -> Sequence[SettingsPanelDefinition]:
        """Return settings panel definitions."""
        ...

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return health check definitions to surface in the dashboard."""
        ...

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        """Return framework-level actions."""
        ...

    def get_routes(self) -> Sequence[AdminRouteSpec]:
        """Return route specifications for the admin router."""
        ...

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Called when the admin dashboard boots."""
        ...

    async def on_admin_shutdown(self) -> None:
        """Called when the admin dashboard shuts down."""
        ...

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        """Render a named widget to a typed WidgetViewModel.

        Args:
            widget_name: Name of the widget to render.
            params: Typed, validated widget parameters.
            resolver: Optional DI resolver for lazy dependency injection.

        Returns:
            Ok(WidgetViewModel) with structured content in ``content`` on success.
            Err(WidgetNotFoundError) when the widget name is unknown.
            Err(AdminError) for other expected domain failures.
            Infrastructure exceptions propagate (not caught here).
        """
        ...

    async def render_health_check(
        self,
        check_name: str,
    ) -> Result[HealthCheckPayload, AdminError]:
        """Run a health check and return a structured health-check payload.

        Args:
            check_name: Name of the health check to run (matches check ID
                from ``get_health_definitions``).

        Returns:
            ``Ok(HealthCheckPayload)`` describing the check result on
            success — the host renders it as HTML.
            ``Err(HealthCheckNotFoundError)`` if *check_name* is not served
            by this contributor.
            ``Err(AdminError)`` if the check fails for any other reason.
        """
        ...


@runtime_checkable
class AdminContributorRegistryProtocol(Protocol):
    """Registry that collects and manages admin contributors."""

    def register(self, contributor: AdminContributorProtocol) -> None:
        """Register a contributor."""
        ...

    def get(self, name: str) -> AdminContributorProtocol | None:
        """Get contributor by name."""
        ...

    def get_all(self) -> Sequence[AdminContributorProtocol]:
        """Get all registered contributors, ordered by priority."""
        ...

    def get_by_group(self, group: str) -> Sequence[AdminContributorProtocol]:
        """Get contributors in a specific group."""
        ...


@runtime_checkable
class AdminDashboardProtocol(Protocol):
    """Protocol for the assembled admin dashboard service."""

    async def get_all_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        """Collect widgets from all contributors."""
        ...

    async def get_all_navigation(self) -> Sequence[NavigationContribution]:
        """Collect navigation from all contributors."""
        ...

    async def get_framework_health(self) -> dict[str, object]:
        """Aggregate health from all contributors."""
        ...

    async def execute_action(
        self,
        contributor_id: str,
        action_name: str,
        params: dict[str, object],
        user_permissions: frozenset[str],
    ) -> object:
        """Execute a framework-level action from a contributor.

        Args:
            contributor_id: Identifier of the target contributor.
            action_name: Name of the action to execute.
            params: Parameters forwarded to the action handler.
            user_permissions: Permissions held by the requesting user.

        Returns:
            Whatever the action handler returns.
        """
        ...


__all__ = [
    "AdminContributorProtocol",
    "AdminContributorRegistryProtocol",
    "AdminDashboardProtocol",
]
