"""Unit tests for TasksAdminContributor widget rendering."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.admin import Stat, StatContent
from quadkit.contracts.admin.errors import AdminError, WidgetNotFoundError
from quadkit.contracts.admin.types import WidgetParams, WidgetViewModel
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.result import Err, Ok
from quadkit.tasks.admin.contributor import TasksAdminContributor
from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler
from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler


@pytest.fixture
def mock_tasks_summary_handler() -> MagicMock:
    """Create mock tasks summary handler."""
    handler = MagicMock(spec=WidgetHandlerProtocol)
    handler.get_data = AsyncMock(
        return_value=Ok(
            StatContent(
                stats=(
                    Stat(label="Pending", value="10"),
                    Stat(label="Running", value="5"),
                    Stat(label="Completed", value="100"),
                    Stat(label="Failed", value="2"),
                )
            )
        )
    )
    return handler


@pytest.fixture
def mock_avg_duration_handler() -> MagicMock:
    """Create mock average duration handler."""
    handler = MagicMock(spec=WidgetHandlerProtocol)
    handler.get_data = AsyncMock(
        return_value=Ok(
            StatContent(
                stats=(
                    Stat(label="Avg", value="250.5ms"),
                    Stat(label="P95", value="500.2ms"),
                )
            )
        )
    )
    return handler


@pytest.fixture
def contributor(
    mock_tasks_summary_handler: MagicMock,
    mock_avg_duration_handler: MagicMock,
) -> TasksAdminContributor:
    """Create TasksAdminContributor with mocked handler dependencies."""
    contrib = TasksAdminContributor()
    contrib._handlers = {
        "tasks_summary": mock_tasks_summary_handler,
        "avg_duration": mock_avg_duration_handler,
    }
    return contrib


class TestTasksAdminContributor:
    """Test suite for TasksAdminContributor."""

    @pytest.mark.asyncio
    async def test_render_tasks_summary_widget(
        self,
        contributor: TasksAdminContributor,
        mock_tasks_summary_handler: MagicMock,
    ) -> None:
        """Test rendering the tasks summary widget."""
        params = WidgetParams(time_window_minutes=60)
        result = await contributor.render_widget("tasks_summary", params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)
        assert len(vm.content.stats) == 4

        # Verify handler was called
        mock_tasks_summary_handler.get_data.assert_awaited_once_with(params)

    @pytest.mark.asyncio
    async def test_render_avg_duration_widget(
        self,
        contributor: TasksAdminContributor,
        mock_avg_duration_handler: MagicMock,
    ) -> None:
        """Test rendering the average duration widget."""
        params = WidgetParams(time_window_minutes=60)
        result = await contributor.render_widget("avg_duration", params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)
        assert len(vm.content.stats) == 2

        # Verify handler was called
        mock_avg_duration_handler.get_data.assert_awaited_once_with(params)

    @pytest.mark.asyncio
    async def test_render_unknown_widget_returns_not_found(
        self, contributor: TasksAdminContributor
    ) -> None:
        """Test that rendering an unknown widget returns WidgetNotFoundError."""
        params = WidgetParams()
        result = await contributor.render_widget("unknown_widget", params)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, WidgetNotFoundError)

    @pytest.mark.asyncio
    async def test_render_before_boot_returns_error(
        self, mock_tasks_summary_handler: MagicMock
    ) -> None:
        """Test that render_widget before on_admin_boot returns an AdminError."""
        contributor = TasksAdminContributor()
        result = await contributor.render_widget("tasks_summary", WidgetParams())

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AdminError)

    @pytest.mark.asyncio
    async def test_render_widget_handler_error_propagates(
        self,
        contributor: TasksAdminContributor,
        mock_tasks_summary_handler: MagicMock,
    ) -> None:
        """Test that handler errors propagate through render_widget."""
        error = AdminError("Handler failed")
        mock_tasks_summary_handler.get_data = AsyncMock(return_value=Err(error))

        params = WidgetParams()
        result = await contributor.render_widget("tasks_summary", params)

        assert result.is_err()
        returned_error = result.unwrap_err()
        assert returned_error is error

    def test_get_dashboard_widgets_returns_two_widgets(
        self, contributor: TasksAdminContributor
    ) -> None:
        """Test that contributor returns exactly 2 dashboard widgets."""
        widgets = contributor.get_dashboard_widgets()
        assert len(widgets) == 2

        widget_names = {w.name for w in widgets}
        assert widget_names == {"tasks_summary", "avg_duration"}

    def test_get_navigation_items(self, contributor: TasksAdminContributor) -> None:
        """Test that contributor returns navigation items."""
        nav_items = contributor.get_navigation_items()
        assert len(nav_items) > 0

    def test_get_health_definitions(self, contributor: TasksAdminContributor) -> None:
        """Test that contributor returns health definitions."""
        health_defs = contributor.get_health_definitions()
        assert len(health_defs) > 0

    def test_get_actions(self, contributor: TasksAdminContributor) -> None:
        """Test that contributor returns actions."""
        actions = contributor.get_actions()
        assert len(actions) > 0


class TestTasksWidgetHandlers:
    """Test individual widget handlers return WidgetContent."""

    @pytest.mark.asyncio
    async def test_tasks_summary_handler(self) -> None:
        """Test tasks_summary handler returns StatContent."""
        handler = TasksSummaryWidgetHandler()
        result = await handler.get_data(WidgetParams())
        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert len(content.stats) == 4

    @pytest.mark.asyncio
    async def test_avg_duration_handler(self) -> None:
        """Test avg_duration handler returns StatContent."""
        handler = AvgDurationWidgetHandler()
        result = await handler.get_data(WidgetParams())
        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert len(content.stats) == 2


__all__ = ["TestTasksAdminContributor", "TestTasksWidgetHandlers"]