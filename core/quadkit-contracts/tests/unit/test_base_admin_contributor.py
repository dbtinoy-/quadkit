"""Tests for BaseAdminContributor no-op defaults and execute_action removal (S7)."""

from __future__ import annotations

from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.types import WidgetParams


class MinimalContributor(BaseAdminContributor):
    name = "minimal"
    display_name = "Minimal"


async def test_execute_action_not_on_base_contributor() -> None:
    """execute_action() must not exist on BaseAdminContributor (S7)."""
    c = MinimalContributor()
    assert not hasattr(c, "execute_action"), (
        "execute_action() was removed; it should not appear on BaseAdminContributor"
    )


async def test_execute_action_not_on_protocol() -> None:
    """execute_action() must not exist on AdminContributorProtocol (S7)."""
    from quadkit.contracts.admin.protocols import AdminContributorProtocol
    assert not hasattr(AdminContributorProtocol, "execute_action"), (
        "execute_action() was removed from AdminContributorProtocol"
    )


def test_get_routes_returns_empty() -> None:
    assert list(MinimalContributor().get_routes()) == []


def test_get_resources_returns_empty() -> None:
    assert list(MinimalContributor().get_resources()) == []


def test_get_dashboard_widgets_returns_empty() -> None:
    assert list(MinimalContributor().get_dashboard_widgets()) == []


def test_get_navigation_items_returns_empty() -> None:
    assert list(MinimalContributor().get_navigation_items()) == []


def test_get_management_pages_returns_empty() -> None:
    assert list(MinimalContributor().get_management_pages()) == []


def test_get_settings_panels_returns_empty() -> None:
    assert list(MinimalContributor().get_settings_panels()) == []


def test_get_health_definitions_returns_empty() -> None:
    assert list(MinimalContributor().get_health_definitions()) == []


def test_get_actions_returns_empty() -> None:
    assert list(MinimalContributor().get_actions()) == []


async def test_on_admin_boot_is_noop() -> None:
    c = MinimalContributor()
    await c.on_admin_boot(None)  # type: ignore[arg-type]


async def test_on_admin_shutdown_is_noop() -> None:
    c = MinimalContributor()
    await c.on_admin_shutdown()


async def test_render_widget_returns_not_found_err() -> None:
    c = MinimalContributor()
    result = await c.render_widget("no_such_widget", WidgetParams())
    assert result.is_err()


async def test_render_health_check_returns_not_found_err() -> None:
    c = MinimalContributor()
    result = await c.render_health_check("no_such_check")
    assert result.is_err()


async def test_render_health_check_default_returns_health_check_payload_err() -> None:
    from quadkit.contracts.admin.contributor import BaseAdminContributor
    from quadkit.contracts.admin.errors import HealthCheckNotFoundError

    contributor = BaseAdminContributor()
    result = await contributor.render_health_check("anything")
    assert result.is_err()
    assert isinstance(result.unwrap_err(), HealthCheckNotFoundError)


def test_contributor_id_equals_name() -> None:
    c = MinimalContributor()
    assert c.contributor_id == c.name
