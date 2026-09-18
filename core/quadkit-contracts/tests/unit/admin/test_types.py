"""Tests for admin contract types."""
from __future__ import annotations

import pytest

from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
    SettingsPanelDefinition,
    WidgetCategory,
    WidgetParams,
    WidgetSize,
    WidgetViewModel,
)
from quadkit.contracts.admin.widget_content import MessageContent, WidgetKind
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol


class TestWidgetSize:
    def test_values(self) -> None:
        assert WidgetSize.SMALL == "small"
        assert WidgetSize.MEDIUM == "medium"
        assert WidgetSize.LARGE == "large"
        assert WidgetSize.FULL == "full"


class TestWidgetCategory:
    def test_values(self) -> None:
        assert WidgetCategory.HEALTH == "health"
        assert WidgetCategory.METRICS == "metrics"
        assert WidgetCategory.ACTIVITY == "activity"
        assert WidgetCategory.RESOURCES == "resources"
        assert WidgetCategory.CUSTOM == "custom"


class TestPageCategory:
    def test_values(self) -> None:
        assert PageCategory.INFRASTRUCTURE == "infrastructure"
        assert PageCategory.SECURITY == "security"
        assert PageCategory.AI == "ai"
        assert PageCategory.DATA == "data"
        assert PageCategory.MONITORING == "monitoring"
        assert PageCategory.CONFIGURATION == "configuration"


class TestDashboardWidgetDefinition:
    def test_creation(self) -> None:
        widget = DashboardWidgetDefinition(
            name="test_widget",
            title="Test Widget",
            contributor="test",
            render_endpoint="/admin/contrib/test/widgets/test",
            view_kind=WidgetKind.STAT,
        )
        assert widget.name == "test_widget"
        assert widget.title == "Test Widget"
        assert widget.size == WidgetSize.MEDIUM
        assert widget.category == WidgetCategory.CUSTOM
        assert widget.refresh_interval_seconds == 30
        assert widget.order == 100
        assert widget.permission is None

    def test_dashboard_widget_definition_requires_view_kind(self) -> None:
        wdef = DashboardWidgetDefinition(
            name="x",
            title="X",
            contributor="web",
            render_endpoint="/admin/web/widgets/x",
            view_kind=WidgetKind.STAT,
        )
        assert wdef.view_kind is WidgetKind.STAT

    def test_frozen(self) -> None:
        widget = DashboardWidgetDefinition(
            name="w",
            title="W",
            contributor="c",
            render_endpoint="/e",
            view_kind=WidgetKind.STAT,
        )
        try:
            widget.name = "other"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_live_resource_types_defaults_empty(self) -> None:
        widget = DashboardWidgetDefinition(
            name="w", title="W", contributor="c", render_endpoint="/x", view_kind=WidgetKind.STAT
        )
        assert widget.live_resource_types == ()


class TestNavigationContribution:
    def test_creation(self) -> None:
        nav = NavigationContribution(
            label="Cache", url="/admin/framework/cache",
            icon="database", group="infrastructure",
        )
        assert nav.label == "Cache"
        assert nav.order == 100
        assert nav.children == ()
        assert nav.badge_endpoint is None

    def test_with_children(self) -> None:
        child = NavigationContribution(label="Sub", url="/sub")
        parent = NavigationContribution(
            label="Parent", url="/parent", children=(child,),
        )
        assert len(parent.children) == 1
        assert parent.children[0].label == "Sub"


class TestManagementPageDefinition:
    def test_creation(self) -> None:
        page = ManagementPageDefinition(
            name="cache_overview",
            title="Cache Management",
            contributor="cache",
            route_path="/admin/framework/cache",
            handler="example_app.admin.pages:cache_overview",
        )
        assert page.category == PageCategory.INFRASTRUCTURE
        assert page.icon == "settings"
        assert page.permission is None


class TestSettingsPanelDefinition:
    def test_creation(self) -> None:
        panel = SettingsPanelDefinition(
            name="cache_settings",
            title="Cache Configuration",
            contributor="cache",
            route_path="/admin/settings/cache",
            handler="example_app.admin.pages:cache_settings",
        )
        assert panel.category == "General"
        assert panel.order == 100


class TestAdminHealthDefinition:
    def test_creation(self) -> None:
        health = AdminHealthDefinition(
            name="cache_backend",
            contributor="cache",
            component="Cache Backend",
        )
        assert health.check_endpoint is None
        assert health.icon == "heart-pulse"


class TestAdminActionDefinition:
    def test_creation(self) -> None:
        action = AdminActionDefinition(
            name="flush_cache",
            title="Flush All Caches",
            contributor="cache",
            handler="example_app.admin.actions:flush_all",
        )
        assert action.destructive is False
        assert action.confirmation_message is None
        assert action.permission is None
        assert action.category == "operations"

    def test_destructive_action(self) -> None:
        action = AdminActionDefinition(
            name="flush",
            title="Flush",
            contributor="cache",
            handler="some:handler",
            destructive=True,
            confirmation_message="Are you sure?",
            permission="admin:cache:flush",
        )
        assert action.destructive is True
        assert action.confirmation_message == "Are you sure?"


class TestWidgetParams:
    def test_defaults(self) -> None:
        params = WidgetParams()
        assert params.page == 1
        assert params.page_size == 20
        assert params.time_window_minutes == 60
        assert params.raw == ()

    def test_custom_values(self) -> None:
        params = WidgetParams(page=2, page_size=50, time_window_minutes=120, raw=(("k", "v"),))
        assert params.page == 2
        assert params.page_size == 50
        assert params.time_window_minutes == 120
        assert params.raw == (("k", "v"),)

    def test_tenant_id_defaults_to_none(self) -> None:
        params = WidgetParams()
        assert params.tenant_id is None

    def test_tenant_id_settable(self) -> None:
        params = WidgetParams(tenant_id="acme")
        assert params.tenant_id == "acme"

    def test_widget_params_is_frozen(self) -> None:
        params = WidgetParams()
        with pytest.raises((AttributeError, TypeError)):
            params.page = 5  # type: ignore[misc]

    def test_widget_params_raw_is_immutable(self) -> None:
        params = WidgetParams(raw=(("a", "b"), ("c", "d")))
        # Cannot reassign .raw
        with pytest.raises((AttributeError, TypeError)):
            params.raw = ()  # type: ignore[misc]
        # Tuple is already immutable
        assert params.raw == (("a", "b"), ("c", "d"))


class TestWidgetViewModel:
    def test_widget_view_model_carries_structured_content_not_body(self) -> None:
        vm = WidgetViewModel(content=MessageContent(text="ok"))
        assert isinstance(vm.content, MessageContent)
        assert not hasattr(vm, "body")


class TestWidgetProtocols:
    def test_widget_handler_protocol_is_runtime_checkable(self) -> None:
        # runtime_checkable means isinstance() works
        from quadkit.contracts.core.result import Ok

        class FakeHandler:
            async def get_data(self, params: WidgetParams):
                return Ok({"data": "test"})

        # Can check protocol conformance at runtime
        assert isinstance(FakeHandler(), WidgetHandlerProtocol)
