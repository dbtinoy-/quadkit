"""Tests for the backend_ping admin widget handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from quadkit.cache.admin.handlers.backend_ping import BackendPingWidgetHandler
from quadkit.contracts.admin import HealthCheckPayload, WidgetParams
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus


def _fake_cache(reachable: bool, backend_name: str = "memory") -> MagicMock:
    cache = MagicMock()
    cache.backend_name = backend_name
    result = HealthCheckResult(
        component=backend_name,
        status=HealthStatus.HEALTHY if reachable else HealthStatus.UNHEALTHY,
    )
    cache.health_check = AsyncMock(return_value=result)
    return cache


async def test_backend_ping_handler_returns_health_payload() -> None:
    result = await BackendPingWidgetHandler(cache=_fake_cache(True)).get_data(
        WidgetParams()
    )
    content = result.unwrap()
    assert isinstance(content, HealthCheckPayload)
    assert content.component == "cache.backend"
    assert content.latency_ms is not None


async def test_backend_ping_reachable_is_healthy() -> None:
    result = await BackendPingWidgetHandler(cache=_fake_cache(True)).get_data(
        WidgetParams()
    )
    content = result.unwrap()
    assert content.status is HealthStatus.HEALTHY
    assert "memory" in content.detail


async def test_backend_ping_unreachable_is_unhealthy() -> None:
    result = await BackendPingWidgetHandler(cache=_fake_cache(False)).get_data(
        WidgetParams()
    )
    content = result.unwrap()
    assert content.status is HealthStatus.UNHEALTHY


__all__ = [
    "test_backend_ping_handler_returns_health_payload",
    "test_backend_ping_reachable_is_healthy",
    "test_backend_ping_unreachable_is_unhealthy",
]