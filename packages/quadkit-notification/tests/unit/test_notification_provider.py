"""Tests for NotificationProvider Named DI registration."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from quadkit.contracts.notification.protocols import PushChannelProtocol, SMSChannelProtocol
from quadkit.notification.config import (
    FCMDriverConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    TwilioDriverConfig,
)
from quadkit.notification.di.provider import NotificationProvider


class TestNotificationProvider:
    @pytest.fixture
    def mock_container(self) -> MagicMock:
        container = MagicMock()
        container.singleton = MagicMock()
        return container

    @pytest.fixture
    def full_config(self) -> NotificationConfig:
        return NotificationConfig(
            sms_backends=[
                NamedSMSConfig(
                    name="alerts",
                    primary=True,
                    driver="twilio",
                    twilio=TwilioDriverConfig(
                        account_sid="ACtest",
                        auth_token="secret",
                        from_number="+15550000000",
                    ),
                )
            ],
            push_backends=[
                NamedPushConfig(
                    name="mobile",
                    primary=True,
                    driver="fcm",
                    fcm=FCMDriverConfig(server_key="test-key"),
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_registers_named_sms_binding(self, mock_container, full_config) -> None:
        provider = NotificationProvider(config=full_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        sms_named = [
            c for c in calls
            if c.args and c.args[0] is SMSChannelProtocol and c.kwargs.get("name") == "alerts"
        ]
        assert len(sms_named) == 1

    @pytest.mark.asyncio
    async def test_registers_unnamed_sms_for_primary(self, mock_container, full_config) -> None:
        provider = NotificationProvider(config=full_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        sms_unnamed = [
            c for c in calls
            if c.args
            and c.args[0] is SMSChannelProtocol
            and not c.kwargs.get("name")
        ]
        assert len(sms_unnamed) >= 1

    @pytest.mark.asyncio
    async def test_registers_named_push_binding(self, mock_container, full_config) -> None:
        provider = NotificationProvider(config=full_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        push_named = [
            c for c in calls
            if c.args and c.args[0] is PushChannelProtocol and c.kwargs.get("name") == "mobile"
        ]
        assert len(push_named) == 1

    @pytest.mark.asyncio
    async def test_empty_config_skips_registration(self, mock_container) -> None:
        provider = NotificationProvider(config=NotificationConfig())
        await provider.register(mock_container)
        # Only NotificationConfig singleton registered — no channel bindings
        calls = mock_container.singleton.call_args_list
        channel_calls = [
            c for c in calls
            if c.args and c.args[0] in (SMSChannelProtocol, PushChannelProtocol)
        ]
        assert len(channel_calls) == 0


    @pytest.mark.asyncio
    async def test_health_check_no_backends_returns_healthy(self) -> None:
        provider = NotificationProvider(config=NotificationConfig())
        result = await provider.health_check()
        from quadkit.contracts.core import HealthStatus
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "notification"

    @pytest.mark.asyncio
    async def test_health_check_aggregates_backends(self, full_config) -> None:
        provider = NotificationProvider(config=full_config)
        mock_container = MagicMock()
        mock_container.singleton = MagicMock()
        await provider.register(mock_container)
        # Services are registered but not booted — health_check should run without error
        result = await provider.health_check()
        from quadkit.contracts.core import HealthStatus
        assert result.component == "notification"
        assert result.status in (HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)


__all__ = ["TestNotificationProvider"]
