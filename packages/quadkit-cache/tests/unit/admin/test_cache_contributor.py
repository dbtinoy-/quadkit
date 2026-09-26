"""Tests for cache admin contributor."""

from __future__ import annotations

import pytest

from quadkit.cache.admin.contributor import CacheAdminContributor
from quadkit.contracts.admin import (
    HealthCheckPayload,
    Stat,
    StatContent,
    Tone,
    WidgetParams,
)
from quadkit.contracts.admin.errors import WidgetNotFoundError
from quadkit.contracts.admin.types import WidgetViewModel
from quadkit.contracts.core.health import HealthStatus
from quadkit.result import Err, Ok


class TestCacheAdminContributor:
    """Test suite for CacheAdminContributor."""

    @pytest.fixture
    def contributor(self) -> CacheAdminContributor:
        """Create contributor with mocked handlers returning WidgetContent."""
        from unittest.mock import AsyncMock, MagicMock

        hit_miss = MagicMock()
        hit_miss.get_data = AsyncMock(
            return_value=Ok(
                StatContent(
                    stats=(
                        Stat(
                            label="Hit Rate (60m)",
                            value="83.3%",
                            tone=Tone.SUCCESS,
                        ),
                        Stat(label="Hits", value="100"),
                        Stat(label="Misses", value="20"),
                    )
                )
            )
        )
        eviction = MagicMock()
        eviction.get_data = AsyncMock(
            return_value=Ok(
                StatContent(
                    stats=(
                        Stat(label="Evictions/sec", value="0.5/s"),
                        Stat(label="Total evictions", value="30"),
                    )
                )
            )
        )
        ping = MagicMock()
        ping.get_data = AsyncMock(
            return_value=Ok(
                HealthCheckPayload(
                    status=HealthStatus.HEALTHY,
                    component="cache.backend",
                    detail="memory",
                    latency_ms=1.23,
                )
            )
        )

        contrib = CacheAdminContributor()
        contrib._handlers = {
            "hit_miss_ratio": hit_miss,
            "eviction_rate": eviction,
            "backend_ping": ping,
        }
        return contrib

    def test_contributor_metadata(self, contributor: CacheAdminContributor) -> None:
        """Test contributor metadata properties."""
        assert contributor.name == "cache"
        assert contributor.display_name == "Cache"
        assert contributor.group == "infrastructure"
        assert contributor.icon == "zap"
        assert contributor.priority == 20

    def test_dashboard_widgets_count(self, contributor: CacheAdminContributor) -> None:
        """Test that contributor returns all three widgets."""
        widgets = contributor.get_dashboard_widgets()
        widget_names = [w.name for w in widgets]
        assert "hit_miss_ratio" in widget_names
        assert "eviction_rate" in widget_names
        assert "backend_ping" in widget_names
        assert len(widgets) == 3

    @pytest.mark.asyncio
    async def test_render_hit_miss_ratio_widget(
        self, contributor: CacheAdminContributor
    ) -> None:
        """Test rendering the hit/miss ratio widget."""
        params = WidgetParams(time_window_minutes=60)
        result = await contributor.render_widget("hit_miss_ratio", params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm, WidgetViewModel)
        assert isinstance(vm.content, StatContent)
        assert vm.content.stats[0].value == "83.3%"
        assert vm.content.stats[0].tone is Tone.SUCCESS

    @pytest.mark.asyncio
    async def test_render_eviction_rate_widget(
        self, contributor: CacheAdminContributor
    ) -> None:
        """Test rendering the eviction rate widget."""
        params = WidgetParams()
        result = await contributor.render_widget("eviction_rate", params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm.content, StatContent)
        assert vm.content.stats[0].value == "0.5/s"

    @pytest.mark.asyncio
    async def test_render_backend_ping_widget(
        self, contributor: CacheAdminContributor
    ) -> None:
        """Test rendering the backend ping widget."""
        params = WidgetParams()
        result = await contributor.render_widget("backend_ping", params)

        assert result.is_ok()
        vm = result.unwrap()
        assert isinstance(vm.content, HealthCheckPayload)
        assert vm.content.status is HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_render_unknown_widget_returns_not_found(
        self, contributor: CacheAdminContributor
    ) -> None:
        """Test that rendering an unknown widget returns WidgetNotFoundError."""
        params = WidgetParams()
        result = await contributor.render_widget("unknown_widget", params)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, WidgetNotFoundError)

    @pytest.mark.asyncio
    async def test_render_widget_handler_error_propagates(
        self, contributor: CacheAdminContributor
    ) -> None:
        """Test that handler errors propagate through render_widget."""
        from unittest.mock import AsyncMock

        from quadkit.contracts.infra.cache.exceptions import CacheError

        error = CacheError("Backend unavailable")
        handler = contributor._handlers["hit_miss_ratio"]
        assert handler is not None
        handler.get_data = AsyncMock(return_value=Err(error))  # type: ignore[attr-defined]

        params = WidgetParams()
        result = await contributor.render_widget("hit_miss_ratio", params)

        assert result.is_err()
        returned_error = result.unwrap_err()
        assert returned_error is error

    @pytest.mark.asyncio
    async def test_render_widget_no_handlers_returns_not_found(self) -> None:
        """Test that missing handler registry returns not found."""
        contributor = CacheAdminContributor()

        params = WidgetParams()
        result = await contributor.render_widget("hit_miss_ratio", params)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), WidgetNotFoundError)


__all__ = ["TestCacheAdminContributor"]