"""Tests for quadkit-events admin contributor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.admin import MessageContent, StatContent
from quadkit.contracts.admin.errors import WidgetNotFoundError
from quadkit.contracts.admin.types import WidgetParams, WidgetViewModel
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.events.admin.contributor import EventsAdminContributor
from quadkit.events.admin.handlers.dead_letter_count import (
    DeadLetterCountWidgetHandler,
)
from quadkit.events.admin.handlers.events_throughput import (
    EventsThroughputWidgetHandler,
)
from quadkit.result import Ok


class TestEventsAdminContributor:
    """Tests for EventsAdminContributor."""

    @pytest.fixture
    def mock_throughput_handler(self) -> MagicMock:
        """Mock EventsThroughputWidgetHandler returning MessageContent."""
        handler = MagicMock(spec=WidgetHandlerProtocol)
        handler.get_data = AsyncMock(
            return_value=Ok(
                MessageContent(text="stub", tone="default")
            )
        )
        return handler

    @pytest.fixture
    def mock_dead_letter_handler(self) -> MagicMock:
        """Mock DeadLetterCountWidgetHandler returning StatContent."""
        handler = MagicMock(spec=WidgetHandlerProtocol)
        handler.get_data = AsyncMock(return_value=Ok(StatContent(stats=())))
        return handler

    @pytest.fixture
    def mock_container(
        self,
        mock_throughput_handler: MagicMock,
        mock_dead_letter_handler: MagicMock,
    ) -> MagicMock:
        """Mock container that resolves handlers."""
        container = MagicMock()
        handler_map = {
            EventsThroughputWidgetHandler: mock_throughput_handler,
            DeadLetterCountWidgetHandler: mock_dead_letter_handler,
        }
        container.resolve = AsyncMock(side_effect=handler_map.get)
        return container

    @pytest.fixture
    def contributor(
        self,
        mock_container: MagicMock,
    ) -> EventsAdminContributor:
        """Create contributor booted with the mocked handlers via container."""
        return EventsAdminContributor()

    @pytest.fixture
    async def booted_contributor(
        self,
        contributor: EventsAdminContributor,
        mock_container: MagicMock,
    ) -> EventsAdminContributor:
        """Boot the contributor through the mocked container."""
        await contributor.on_admin_boot(mock_container)
        return contributor

    @pytest.mark.asyncio
    async def test_render_widget_throughput(
        self,
        booted_contributor: EventsAdminContributor,
        mock_throughput_handler: MagicMock,
    ) -> None:
        """Render events_throughput widget passes MessageContent through."""
        result = await booted_contributor.render_widget(
            "events_throughput", WidgetParams()
        )
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, MessageContent)
        mock_throughput_handler.get_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_render_widget_dead_letter(
        self,
        booted_contributor: EventsAdminContributor,
        mock_dead_letter_handler: MagicMock,
    ) -> None:
        """Render dead_letter_count widget passes StatContent through."""
        result = await booted_contributor.render_widget(
            "dead_letter_count", WidgetParams()
        )
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)
        mock_dead_letter_handler.get_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_render_unknown_widget(
        self, booted_contributor: EventsAdminContributor
    ) -> None:
        """Unknown widget name returns WidgetNotFoundError."""
        result = await booted_contributor.render_widget("nonexistent", WidgetParams())
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, WidgetNotFoundError)
        assert error.contributor_name == "events"
        assert error.widget_name == "nonexistent"

    def test_get_dashboard_widgets(self, contributor: EventsAdminContributor) -> None:
        """Contributor returns three dashboard widgets."""
        widgets = contributor.get_dashboard_widgets()
        assert len(widgets) == 3
        names = {w.name for w in widgets}
        assert names == {"events_throughput", "dead_letter_count", "live_events"}

    def test_get_navigation_items(self, contributor: EventsAdminContributor) -> None:
        """Contributor returns navigation items."""
        items = contributor.get_navigation_items()
        assert len(items) > 0
        root = next((i for i in items if i.label == "Events"), None)
        assert root is not None

    def test_get_health_definitions(self, contributor: EventsAdminContributor) -> None:
        """Contributor returns health definitions."""
        defs = contributor.get_health_definitions()
        assert len(defs) > 0


__all__ = [
    "TestEventsAdminContributor",
]
