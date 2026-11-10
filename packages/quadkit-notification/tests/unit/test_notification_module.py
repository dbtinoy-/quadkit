"""Tests for NotificationModule."""

from __future__ import annotations

import pytest

from quadkit.contracts.notification.protocols import PushChannelProtocol, SMSChannelProtocol
from quadkit.di.module import DynamicModule
from quadkit.notification.config import (
    FCMDriverConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    TwilioDriverConfig,
)
from quadkit.notification.di.provider import NotificationProvider
from quadkit.notification.module import NotificationModule


class TestNotificationModule:
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

    def test_configure_returns_dynamic_module(self, full_config) -> None:
        """configure() should return a DynamicModule."""
        result = NotificationModule.configure(full_config)
        assert isinstance(result, DynamicModule)

    def test_configure_exports_sms_protocol(self, full_config) -> None:
        """configure() should export SMSChannelProtocol."""
        result = NotificationModule.configure(full_config)
        assert SMSChannelProtocol in result.exports

    def test_configure_exports_push_protocol(self, full_config) -> None:
        """configure() should export PushChannelProtocol."""
        result = NotificationModule.configure(full_config)
        assert PushChannelProtocol in result.exports

    def test_configure_has_notification_provider(self, full_config) -> None:
        """configure() should have NotificationProvider in providers."""
        result = NotificationModule.configure(full_config)
        assert any(isinstance(p, NotificationProvider) for p in result.providers)

    def test_configure_with_none_config(self) -> None:
        """configure() should accept None config."""
        result = NotificationModule.configure(None)
        assert isinstance(result, DynamicModule)
        assert any(isinstance(p, NotificationProvider) for p in result.providers)

    def test_stub_returns_dynamic_module(self) -> None:
        """stub() should return a DynamicModule."""
        result = NotificationModule.stub()
        assert isinstance(result, DynamicModule)

    def test_stub_exports_sms_protocol(self) -> None:
        """stub() should export SMSChannelProtocol."""
        result = NotificationModule.stub()
        assert SMSChannelProtocol in result.exports

    def test_stub_exports_push_protocol(self) -> None:
        """stub() should export PushChannelProtocol."""
        result = NotificationModule.stub()
        assert PushChannelProtocol in result.exports

    def test_stub_has_notification_provider(self) -> None:
        """stub() should have NotificationProvider in providers."""
        result = NotificationModule.stub()
        assert any(isinstance(p, NotificationProvider) for p in result.providers)

    def test_stub_uses_empty_config(self) -> None:
        """stub() should use an empty NotificationConfig by default."""
        result = NotificationModule.stub()
        provider = next(p for p in result.providers if isinstance(p, NotificationProvider))
        assert provider._config == NotificationConfig()


__all__ = ["TestNotificationModule"]
