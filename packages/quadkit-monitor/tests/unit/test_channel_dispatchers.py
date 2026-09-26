"""Tests for channel dispatchers (PagerDuty, Slack, WeeklyDigest)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
from quadkit.contracts.web.http_protocols import HTTPClientProtocol
from quadkit.result import Ok


class TestPagerDutyAlertDispatcher:
    @pytest.fixture()
    def http_client(self) -> AsyncMock:
        client = AsyncMock(spec=HTTPClientProtocol)
        resp = MagicMock()
        resp.status = 202
        resp.body = b'{"status":"success"}'
        client.request = AsyncMock(return_value=resp)
        return client

    @pytest.mark.asyncio
    async def test_sends_event_to_pagerduty(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.pagerduty import (
            PagerDutyAlertDispatcher,
        )

        dispatcher = PagerDutyAlertDispatcher(
            integration_key="test-key",
            http_client=http_client,
        )

        await dispatcher.send_alert(
            title="High latency",
            message="p99 > 200ms",
            severity="critical",
            context={"slo_name": "api.p99"},
        )

        http_client.request.assert_awaited_once()
        call_args = http_client.request.await_args
        assert call_args is not None
        assert call_args.kwargs["url"] == "https://events.pagerduty.com/v2/enqueue"
        payload = call_args.kwargs["json"]
        assert payload["routing_key"] == "test-key"
        assert payload["event_action"] == "trigger"
        assert payload["payload"]["summary"] == "High latency: p99 > 200ms"
        assert payload["payload"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_send_metric_alert(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.pagerduty import (
            PagerDutyAlertDispatcher,
        )

        dispatcher = PagerDutyAlertDispatcher(
            integration_key="test-key",
            http_client=http_client,
        )

        await dispatcher.send_metric_alert(
            metric_name="api.latency",
            current_value=500.0,
            threshold=200.0,
            context={"slo_name": "api.p99"},
        )

        http_client.request.assert_awaited_once()
        payload = http_client.request.await_args.kwargs["json"]
        assert "api.latency" in payload["payload"]["summary"]


class TestSlackBusinessHoursDispatcher:
    @pytest.fixture()
    def http_client(self) -> AsyncMock:
        client = AsyncMock(spec=HTTPClientProtocol)
        resp = MagicMock()
        resp.status = 200
        client.request = AsyncMock(return_value=resp)
        return client

    @pytest.mark.asyncio
    async def test_sends_alert_during_business_hours(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.slack_business_hours import (
            SlackBusinessHoursDispatcher,
        )

        dispatcher = SlackBusinessHoursDispatcher(
            webhook_url="https://hooks.slack.com/test",
            timezone="UTC",
            business_hours=(0, 24),  # Always within business hours
            http_client=http_client,
        )

        await dispatcher.send_alert(
            title="P1 alert",
            message="Something needs attention",
            severity="high",
        )

        http_client.request.assert_awaited_once()
        payload = http_client.request.await_args.kwargs["json"]
        assert "P1 alert" in payload["text"]

    @pytest.mark.asyncio
    async def test_queues_outside_business_hours(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.slack_business_hours import (
            SlackBusinessHoursDispatcher,
        )

        dispatcher = SlackBusinessHoursDispatcher(
            webhook_url="https://hooks.slack.com/test",
            timezone="UTC",
            business_hours=(0, 0),  # Empty window — always outside, clock-independent
            http_client=http_client,
        )

        await dispatcher.send_alert(
            title="Night alert",
            message="Happened at night",
            severity="high",
        )

        # Not sent immediately — queued until business hours
        http_client.request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_flush_queue_sends_queued(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.slack_business_hours import (
            SlackBusinessHoursDispatcher,
        )

        dispatcher = SlackBusinessHoursDispatcher(
            webhook_url="https://hooks.slack.com/test",
            timezone="UTC",
            business_hours=(0, 0),  # Empty window — always outside, clock-independent
            http_client=http_client,
        )

        await dispatcher.send_alert("A1", "msg1", "high")
        await dispatcher.send_alert("A2", "msg2", "medium")
        http_client.request.assert_not_awaited()

        await dispatcher.flush_queue()
        assert http_client.request.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_metric_alert(self, http_client: AsyncMock):
        from quadkit.monitor.alerts.channels.slack_business_hours import (
            SlackBusinessHoursDispatcher,
        )

        dispatcher = SlackBusinessHoursDispatcher(
            webhook_url="https://hooks.slack.com/test",
            timezone="UTC",
            business_hours=(0, 24),  # Always within business hours
            http_client=http_client,
        )

        await dispatcher.send_metric_alert("cpu", 90.0, 80.0)
        http_client.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_respects_timezone_parameter(self, http_client: AsyncMock):
        from datetime import timezone
        from unittest.mock import patch

        import zoneinfo

        import quadkit.monitor.alerts.channels.slack_business_hours as mod
        from quadkit.monitor.alerts.channels.slack_business_hours import (
            SlackBusinessHoursDispatcher,
        )

        def now_side_effect(tz=None):
            if tz is timezone.utc:
                return datetime(2026, 1, 1, 2, 0, 0, tzinfo=tz)
            return datetime(2026, 1, 1, 11, 0, 0, tzinfo=tz)

        with patch.object(mod, 'datetime') as mock_dt:
            mock_dt.now.side_effect = now_side_effect

            dispatcher = SlackBusinessHoursDispatcher(
                webhook_url="https://hooks.slack.com/test",
                timezone="Asia/Tokyo",
                business_hours=(9, 18),
                http_client=http_client,
            )

            # 02:00 UTC = 11:00 Tokyo. Tokyo 11:00 is within 9-18 business hours,
            # so the alert should be sent (not queued). Buggy code uses UTC and
            # sees hour=2, queuing instead.
            await dispatcher.send_alert(
                title="Tokyo hours",
                message="Should send during Tokyo business hours",
                severity="high",
            )

            http_client.request.assert_awaited_once()


class TestWeeklyDigestDispatcher:
    @pytest.fixture()
    def cache_backend(self) -> AsyncMock:
        backend = AsyncMock()
        backend.get = AsyncMock(return_value=Ok(None))
        backend.set = AsyncMock()
        backend.delete = AsyncMock()
        return backend

    @pytest.fixture()
    def flush_dispatcher(self) -> AsyncMock:
        d = AsyncMock(spec=AlertDispatcherProtocol)
        d.send_alert = AsyncMock()
        return d

    @pytest.mark.asyncio
    async def test_accumulates_alerts_in_buffer(
        self,
        cache_backend: AsyncMock,
        flush_dispatcher: AsyncMock,
    ):
        from quadkit.monitor.alerts.channels.weekly_digest import (
            WeeklyDigestDispatcher,
        )

        dispatcher = WeeklyDigestDispatcher(
            buffer_store=cache_backend,
            flush_dispatcher=flush_dispatcher,
            digest_key="test:digest",
        )

        await dispatcher.send_alert("A1", "msg1", "low")
        await dispatcher.send_alert("A2", "msg2", "medium")

        cache_backend.set.assert_awaited()
        flush_dispatcher.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_flush_sends_digest(
        self,
        cache_backend: AsyncMock,
        flush_dispatcher: AsyncMock,
    ):
        from quadkit.monitor.alerts.channels.weekly_digest import (
            WeeklyDigestDispatcher,
        )

        # Buffer has existing alerts
        cache_backend.get = AsyncMock(
            return_value=Ok('[{"title":"A1","message":"m1","severity":"low"}]')
        )

        dispatcher = WeeklyDigestDispatcher(
            buffer_store=cache_backend,
            flush_dispatcher=flush_dispatcher,
            digest_key="test:digest",
        )

        await dispatcher.send_alert("A2", "m2", "medium")
        await dispatcher.flush()

        flush_dispatcher.send_alert.assert_awaited_once()
        assert cache_backend.delete.await_args is not None
