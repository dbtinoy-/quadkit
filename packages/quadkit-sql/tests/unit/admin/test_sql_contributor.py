"""Unit tests for SqlAdminContributor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.admin import HealthCheckPayload, StatContent
from quadkit.contracts.admin.errors import WidgetNotFoundError
from quadkit.contracts.admin.types import WidgetParams, WidgetViewModel
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.contracts.core.health import HealthStatus
from quadkit.result import Ok
from quadkit.sql.admin.contributor import SqlAdminContributor
from quadkit.sql.admin.handlers.migration_status import MigrationStatusWidgetHandler
from quadkit.sql.admin.handlers.pool_utilization import PoolUtilizationWidgetHandler
from quadkit.sql.admin.handlers.query_stats import QueryStatsWidgetHandler


class _FakeMigrations:
    """Fake migration manager for widget tests."""

    def __init__(self, applied: list[str], pending: list[str]) -> None:
        self._applied = applied
        self._pending = pending

    async def get_applied_migrations(self) -> list[str]:
        return self._applied

    async def get_pending_migrations(self) -> list[str]:
        return self._pending


class TestSqlAdminContributor:
    """Tests for SqlAdminContributor widget rendering."""

    @pytest.fixture
    def mock_pool_handler(self) -> MagicMock:
        """Create a mock pool utilization handler."""
        h = MagicMock(spec=WidgetHandlerProtocol)
        h.get_data = AsyncMock(return_value=Ok(StatContent(stats=())))
        return h

    @pytest.fixture
    def mock_query_handler(self) -> MagicMock:
        """Create a mock query stats handler."""
        h = MagicMock(spec=WidgetHandlerProtocol)
        h.get_data = AsyncMock(return_value=Ok(StatContent(stats=())))
        return h

    @pytest.fixture
    def mock_migration_handler(self) -> MagicMock:
        """Create a mock migration status handler."""
        h = MagicMock(spec=WidgetHandlerProtocol)
        h.get_data = AsyncMock(
            return_value=Ok(
                HealthCheckPayload(
                    status=HealthStatus.HEALTHY,
                    component="sql.migrations",
                    detail="Version 20240101_000001; 5 applied",
                )
            )
        )
        return h

    @pytest.fixture
    def contributor(
        self,
        mock_pool_handler: MagicMock,
        mock_query_handler: MagicMock,
        mock_migration_handler: MagicMock,
    ) -> SqlAdminContributor:
        """Create a contributor with mocked handler dependencies."""
        contrib = SqlAdminContributor()
        contrib._handlers = {
            "pool_utilization": mock_pool_handler,
            "query_stats": mock_query_handler,
            "migration_status": mock_migration_handler,
        }
        return contrib

    @pytest.mark.asyncio
    async def test_render_pool_utilization_widget(
        self,
        contributor: SqlAdminContributor,
        mock_pool_handler: MagicMock,
    ) -> None:
        """Test render_widget returns StatContent for pool_utilization."""
        result = await contributor.render_widget("pool_utilization", WidgetParams())
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)
        mock_pool_handler.get_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_render_query_stats_widget(
        self,
        contributor: SqlAdminContributor,
        mock_query_handler: MagicMock,
    ) -> None:
        """Test render_widget returns StatContent for query_stats."""
        result = await contributor.render_widget("query_stats", WidgetParams())
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm.content, StatContent)
        mock_query_handler.get_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_render_migration_status_widget(
        self,
        contributor: SqlAdminContributor,
        mock_migration_handler: MagicMock,
    ) -> None:
        """Test render_widget returns HealthCheckPayload for migration_status."""
        result = await contributor.render_widget("migration_status", WidgetParams())
        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm.content, HealthCheckPayload)
        mock_migration_handler.get_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_widget_returns_not_found(
        self, contributor: SqlAdminContributor
    ) -> None:
        """Test that unknown widget names return WidgetNotFoundError."""
        result = await contributor.render_widget("nonexistent", WidgetParams())
        assert result.is_err()
        assert isinstance(result.unwrap_err(), WidgetNotFoundError)

    def test_get_dashboard_widgets_returns_three(
        self, contributor: SqlAdminContributor
    ) -> None:
        """Test that exactly three dashboard widgets are registered."""
        widgets = contributor.get_dashboard_widgets()
        assert len(widgets) == 3
        widget_names = {w.name for w in widgets}
        assert widget_names == {
            "pool_utilization",
            "query_stats",
            "migration_status",
        }

    def test_get_navigation_items_not_empty(
        self, contributor: SqlAdminContributor
    ) -> None:
        """Test that navigation items are returned."""
        items = contributor.get_navigation_items()
        assert len(items) > 0
        assert any(item.label == "Database" for item in items)

    def test_get_health_definitions_not_empty(
        self, contributor: SqlAdminContributor
    ) -> None:
        """Test that health definitions are returned."""
        defs = contributor.get_health_definitions()
        assert len(defs) > 0
        assert any("connectivity" in d.name for d in defs)

    def test_contributor_name_is_sql(self, contributor: SqlAdminContributor) -> None:
        """Test that contributor name is 'sql'."""
        assert contributor.name == "sql"

    def test_contributor_metadata(self, contributor: SqlAdminContributor) -> None:
        """Test contributor metadata fields."""
        assert contributor.display_name == "Database"
        assert contributor.group == "infrastructure"
        assert contributor.icon == "database"
        assert contributor.priority == 15


class TestSqlWidgetHandlers:
    """Test individual widget handlers return WidgetContent."""

    @pytest.mark.asyncio
    async def test_pool_utilization_handler(self) -> None:
        """Test pool_utilization handler returns StatContent."""
        handler = PoolUtilizationWidgetHandler(db=None)  # type: ignore[arg-type]
        result = await handler.get_data(WidgetParams())
        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert content.stats[0].value == "Unavailable"

    @pytest.mark.asyncio
    async def test_query_stats_handler(self) -> None:
        """Test query_stats handler returns StatContent."""
        handler = QueryStatsWidgetHandler(db=None)  # type: ignore[arg-type]
        result = await handler.get_data(WidgetParams())
        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert content.stats[0].value == "Unavailable"

    @pytest.mark.asyncio
    async def test_migration_status_handler(self) -> None:
        """Test migration_status handler returns StatContent."""
        handler = MigrationStatusWidgetHandler(
            migration_manager=_FakeMigrations(["a", "b"], [])
        )
        result = await handler.get_data(WidgetParams())
        assert result.is_ok()
        content = result.unwrap()
        assert isinstance(content, StatContent)
        assert content.stats[0].value == "2 applied"
        assert content.stats[1].value == "0 pending"
