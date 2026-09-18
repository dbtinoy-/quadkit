"""Tests for admin contract protocols."""

from __future__ import annotations

from collections.abc import Sequence

from quadkit.contracts.admin.protocols import (
    AdminContributorProtocol,
    AdminContributorRegistryProtocol,
    AdminDashboardProtocol,
)
from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    AdminRouteSpec,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    SettingsPanelDefinition,
)


class FakeContributor:
    """Minimal implementation to verify protocol compliance."""

    name = "fake"
    display_name = "Fake"
    group = "test"
    icon = "box"
    priority = 50
    version = "0.0.0"
    package_source = "built-in"
    depends_on: tuple[str, ...] = ()
    required_permissions: frozenset[str] = frozenset()

    @property
    def contributor_id(self) -> str:
        return self.name

    def get_resources(self) -> Sequence[type]:
        return []

    def get_routes(self) -> Sequence[AdminRouteSpec]:
        return []

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        return []

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        return []

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        return []

    def get_settings_panels(self) -> Sequence[SettingsPanelDefinition]:
        return []

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        return []

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        return []

    async def on_admin_boot(self, container: object) -> None:
        pass

    async def on_admin_shutdown(self) -> None:
        pass

    async def execute_action(
        self, action_name: str, params: dict[str, object]
    ) -> object:
        return None

    async def render_widget(
        self,
        widget_name: str,
        params: dict[str, str],
    ) -> object:
        return None

    async def render_health_check(
        self,
        check_name: str,
    ) -> object:
        return None


class TestAdminContributorProtocol:
    def test_runtime_checkable(self) -> None:
        contributor = FakeContributor()
        assert isinstance(contributor, AdminContributorProtocol)

    def test_non_contributor_fails_check(self) -> None:
        assert not isinstance("not a contributor", AdminContributorProtocol)

    def test_properties_accessible(self) -> None:
        contributor = FakeContributor()
        assert contributor.name == "fake"
        assert contributor.display_name == "Fake"
        assert contributor.group == "test"
        assert contributor.icon == "box"
        assert contributor.priority == 50


class TestAdminContributorRegistryProtocol:
    def test_runtime_checkable(self) -> None:
        class FakeRegistry:
            def register(self, contributor: object) -> None:
                pass

            def get(self, name: str) -> object:
                return None

            def get_all(self) -> list:
                return []

            def get_by_group(self, group: str) -> list:
                return []

        assert isinstance(FakeRegistry(), AdminContributorRegistryProtocol)


class TestAdminDashboardProtocol:
    def test_runtime_checkable(self) -> None:
        class FakeDashboard:
            async def get_all_widgets(self) -> list:
                return []

            async def get_all_navigation(self) -> list:
                return []

            async def get_framework_health(self) -> dict:
                return {}

            async def execute_action(
                self,
                contributor_id: str,
                action_name: str,
                params: dict[str, object],
                user_permissions: frozenset[str],
            ) -> None:
                return None

        assert isinstance(FakeDashboard(), AdminDashboardProtocol)
