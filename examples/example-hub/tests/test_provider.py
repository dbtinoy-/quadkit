"""Tests for Demo Hub provider readiness reporting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from example_hub.di.provider import HubProvider
from quadkit.contracts.core.health import HealthStatus


class TestHubProviderHealth:
    """Hub readiness must include embedded-child failures."""

    @pytest.mark.asyncio
    async def test_unbooted_fleet_is_not_reported_healthy(self) -> None:
        result = await HubProvider().health_check()

        assert result.status == HealthStatus.DEGRADED
        assert result.details == {"mounted": 0, "failures": 0}

    @pytest.mark.asyncio
    async def test_fleet_failures_degrade_hub_readiness(self) -> None:
        provider = HubProvider()
        provider._fleet = SimpleNamespace(
            mounted={"event-timeline": True},
            failures={"broken-demo": "RuntimeError: boot failed"},
        )

        result = await provider.health_check()

        assert result.status == HealthStatus.DEGRADED
        assert result.details == {"mounted": 1, "failures": 1}

    @pytest.mark.asyncio
    async def test_fully_mounted_fleet_is_healthy(self) -> None:
        provider = HubProvider()
        provider._fleet = SimpleNamespace(
            mounted={"event-timeline": True},
            failures={},
        )

        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.details == {"mounted": 1, "failures": 0}
