"""Tests for web admin widget rendering.

Tests the WebAdminContributor widget handler dispatch, renderer,
and WidgetContent integration.
"""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import HealthCheckPayload, StatContent
from quadkit.contracts.admin.errors import WidgetNotFoundError
from quadkit.contracts.admin.types import WidgetParams, WidgetViewModel
from quadkit.web.admin.contributor import WebAdminContributor
from quadkit.web.admin.widgets import (
    ActiveConnectionsWidgetHandler,
    RequestRateWidgetHandler,
    ServerStatusWidgetHandler,
)


class TestWebAdminContributor:
    """Test WebAdminContributor widget rendering."""

    @pytest.fixture
    async def contributor(self) -> WebAdminContributor:
        """Create a contributor instance with mock dependencies."""
        from unittest.mock import AsyncMock, MagicMock

        from quadkit.contracts.core.health import HealthStatus
        from quadkit.result import Ok

        mock_server_status = MagicMock(spec=ServerStatusWidgetHandler)
        mock_server_status.get_data = AsyncMock(
            return_value=Ok(
                HealthCheckPayload(
                    status=HealthStatus.HEALTHY,
                    component="HTTP Server",
                    detail="v1.0.0, up 3600s",
                )
            )
        )

        mock_connections = MagicMock(spec=ActiveConnectionsWidgetHandler)
        mock_connections.get_data = AsyncMock(
            return_value=Ok(
                StatContent(
                    stats=(
                        # Most stats would be tuples of Stat objects, but a
                        # MagicMock content is enough to prove pass-through.
                    )
                )
            )
        )

        mock_request_rate = MagicMock(spec=RequestRateWidgetHandler)
        mock_request_rate.get_data = AsyncMock(return_value=Ok(StatContent(stats=())))

        handler_map = {
            ServerStatusWidgetHandler: mock_server_status,
            ActiveConnectionsWidgetHandler: mock_connections,
            RequestRateWidgetHandler: mock_request_rate,
        }
        contributor = WebAdminContributor()
        mock_container = MagicMock()
        mock_container.resolve = AsyncMock(side_effect=handler_map.get)
        await contributor.on_admin_boot(mock_container)
        return contributor

    @pytest.fixture
    def widget_params(self) -> WidgetParams:
        """Create widget parameters."""
        return WidgetParams()

    @pytest.mark.asyncio
    async def test_render_server_status_widget(
        self,
        contributor: WebAdminContributor,
        widget_params: WidgetParams,
    ) -> None:
        """Test rendering the server_status widget."""
        result = await contributor.render_widget("server_status", widget_params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, HealthCheckPayload)

    @pytest.mark.asyncio
    async def test_render_active_connections_widget(
        self,
        contributor: WebAdminContributor,
        widget_params: WidgetParams,
    ) -> None:
        """Test rendering the active_connections widget."""
        result = await contributor.render_widget("active_connections", widget_params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)

    @pytest.mark.asyncio
    async def test_render_request_rate_widget(
        self,
        contributor: WebAdminContributor,
        widget_params: WidgetParams,
    ) -> None:
        """Test rendering the request_rate widget."""
        result = await contributor.render_widget("request_rate", widget_params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)

    @pytest.mark.asyncio
    async def test_render_unknown_widget_returns_error(
        self,
        contributor: WebAdminContributor,
        widget_params: WidgetParams,
    ) -> None:
        """Test that rendering an unknown widget returns WidgetNotFoundError."""
        result = await contributor.render_widget("unknown_widget", widget_params)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, WidgetNotFoundError)
        assert "unknown_widget" in str(error)
        assert "web" in str(error)

    def test_contributor_metadata(self, contributor: WebAdminContributor) -> None:
        """Test contributor metadata."""
        assert contributor.name == "web"
        assert contributor.display_name == "Web Server"
        assert contributor.group == "infrastructure"
        assert contributor.priority == 10

    def test_dashboard_widgets_defined(self, contributor: WebAdminContributor) -> None:
        """Test that dashboard widgets are defined."""
        widgets = contributor.get_dashboard_widgets()

        assert len(widgets) == 3
        widget_names = [w.name for w in widgets]
        assert "server_status" in widget_names
        assert "active_connections" in widget_names
        assert "request_rate" in widget_names

    def test_navigation_items_defined(self, contributor: WebAdminContributor) -> None:
        """Test that navigation items are defined."""
        nav_items = contributor.get_navigation_items()

        assert len(nav_items) > 0
        assert nav_items[0].label == "Web"

    def test_health_definitions_defined(self, contributor: WebAdminContributor) -> None:
        """Test that health definitions are defined."""
        health_defs = contributor.get_health_definitions()

        assert len(health_defs) > 0
        health_names = [h.name for h in health_defs]
        assert "web.server" in health_names

    def test_actions_defined(self, contributor: WebAdminContributor) -> None:
        """Test that admin actions are defined."""
        actions = contributor.get_actions()

        assert len(actions) > 0
        action_names = [a.name for a in actions]
        assert "reload_routes" in action_names


class TestWidgetHandlers:
    """Test individual widget handlers return WidgetContent."""

    @pytest.mark.asyncio
    async def test_server_status_handler(self) -> None:
        """Test server_status handler returns StatContent with process info."""
        handler = ServerStatusWidgetHandler()
        result = await handler.get_data(WidgetParams())

        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert len(content.stats) == 3

    @pytest.mark.asyncio
    async def test_active_connections_handler(self) -> None:
        """Test active_connections handler returns StatContent."""
        handler = ActiveConnectionsWidgetHandler()
        result = await handler.get_data(WidgetParams())

        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert content.stats[0].label == "Active"

    @pytest.mark.asyncio
    async def test_request_rate_handler(self) -> None:
        """Test request_rate handler returns StatContent."""
        handler = RequestRateWidgetHandler()
        result = await handler.get_data(WidgetParams())

        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert content.stats[0].label == "Requests/sec"


__all__ = [
    "TestWebAdminContributor",
    "TestWidgetHandlers",
]
