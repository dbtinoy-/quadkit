"""Tests for TierAwareAlertDispatcher."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.monitor.projection_tier import ProjectionTier
from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
from quadkit.monitor.alerts.tier_dispatcher import TierAwareAlertDispatcher


class TestTierAwareAlertDispatcher:
    @pytest.fixture()
    def p0_channel(self) -> AsyncMock:
        m = AsyncMock(spec=AlertDispatcherProtocol)
        m.send_alert = AsyncMock()
        m.send_metric_alert = AsyncMock()
        return m

    @pytest.fixture()
    def default_channel(self) -> AsyncMock:
        m = AsyncMock(spec=AlertDispatcherProtocol)
        m.send_alert = AsyncMock()
        m.send_metric_alert = AsyncMock()
        return m

    @pytest.fixture()
    def dispatcher(
        self,
        p0_channel: AsyncMock,
        default_channel: AsyncMock,
    ) -> TierAwareAlertDispatcher:
        return TierAwareAlertDispatcher(
            channels={ProjectionTier.P0_PAGE: p0_channel},
            default_dispatcher=default_channel,
        )

    @pytest.mark.asyncio
    async def test_routes_p0_to_p0_channel(
        self,
        dispatcher: TierAwareAlertDispatcher,
        p0_channel: AsyncMock,
        default_channel: AsyncMock,
    ):
        await dispatcher.send_alert(
            title="P0 alert",
            message="Something is on fire",
            severity="critical",
            context={"tier": "p0_page"},
        )
        p0_channel.send_alert.assert_awaited_once_with(
            "P0 alert", "Something is on fire", "critical", {"tier": "p0_page"},
        )
        default_channel.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_routes_unconfigured_tier_to_default(
        self,
        dispatcher: TierAwareAlertDispatcher,
        p0_channel: AsyncMock,
        default_channel: AsyncMock,
    ):
        await dispatcher.send_alert(
            title="P2 alert",
            message="Weekly summary",
            severity="low",
            context={"tier": "p2_digest"},
        )
        p0_channel.send_alert.assert_not_awaited()
        default_channel.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_tier_in_context_uses_default(
        self,
        dispatcher: TierAwareAlertDispatcher,
        p0_channel: AsyncMock,
        default_channel: AsyncMock,
    ):
        await dispatcher.send_alert("test", "msg", "low")
        default_channel.send_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_metric_alert_routes_by_tier(
        self,
        dispatcher: TierAwareAlertDispatcher,
        p0_channel: AsyncMock,
        default_channel: AsyncMock,
    ):
        await dispatcher.send_metric_alert(
            metric_name="api.latency",
            current_value=500.0,
            threshold=200.0,
            context={"tier": "p0_page"},
        )
        p0_channel.send_metric_alert.assert_awaited_once()
        default_channel.send_metric_alert.assert_not_awaited()
