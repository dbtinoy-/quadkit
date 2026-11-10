"""Tests for quadkit.notification config."""

from __future__ import annotations

import pytest

from quadkit.notification.config import (
    FCMDriverConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    TwilioDriverConfig,
)


class TestTwilioDriverConfig:
    """Tests for TwilioDriverConfig."""

    def test_defaults(self) -> None:
        """Test TwilioDriverConfig defaults."""
        cfg = TwilioDriverConfig(
            account_sid="AC123", auth_token="token123", from_number="+1234567890"
        )
        assert cfg.account_sid == "AC123"
        assert cfg.auth_token.get_secret_value() == "token123"
        assert cfg.from_number == "+1234567890"
        assert cfg.timeout == 30  # DEFAULT_TWILIO_TIMEOUT

    def test_custom_timeout(self) -> None:
        """Test TwilioDriverConfig with custom timeout."""
        cfg = TwilioDriverConfig(
            account_sid="AC123",
            auth_token="token123",
            from_number="+1234567890",
            timeout=60,
        )
        assert cfg.timeout == 60


class TestFCMDriverConfig:
    """Tests for FCMDriverConfig."""

    def test_defaults(self) -> None:
        """Test FCMDriverConfig defaults."""
        cfg = FCMDriverConfig(server_key="server_key_123")
        assert cfg.server_key.get_secret_value() == "server_key_123"
        assert cfg.timeout == 30  # DEFAULT_FCM_TIMEOUT

    def test_custom_timeout(self) -> None:
        """Test FCMDriverConfig with custom timeout."""
        cfg = FCMDriverConfig(server_key="server_key_123", timeout=60)
        assert cfg.timeout == 60


class TestNamedSMSConfig:
    """Tests for NamedSMSConfig."""

    def test_defaults(self) -> None:
        """Test NamedSMSConfig defaults."""
        cfg = NamedSMSConfig(name="alerts", driver="twilio")
        assert cfg.name == "alerts"
        assert cfg.primary is False
        assert cfg.driver == "twilio"
        assert cfg.twilio is None

    def test_primary_flag(self) -> None:
        """Test NamedSMSConfig with primary=True."""
        cfg = NamedSMSConfig(name="primary", driver="twilio", primary=True)
        assert cfg.primary is True

    def test_with_twilio_config(self) -> None:
        """Test NamedSMSConfig with TwilioDriverConfig."""
        twilio_cfg = TwilioDriverConfig(
            account_sid="AC123", auth_token="token123", from_number="+1234567890"
        )
        cfg = NamedSMSConfig(
            name="alerts", driver="twilio", primary=True, twilio=twilio_cfg
        )
        assert cfg.twilio is not None
        assert cfg.twilio.account_sid == "AC123"


class TestNamedPushConfig:
    """Tests for NamedPushConfig."""

    def test_defaults(self) -> None:
        """Test NamedPushConfig defaults."""
        cfg = NamedPushConfig(name="mobile", driver="fcm")
        assert cfg.name == "mobile"
        assert cfg.primary is False
        assert cfg.driver == "fcm"
        assert cfg.fcm is None

    def test_primary_flag(self) -> None:
        """Test NamedPushConfig with primary=True."""
        cfg = NamedPushConfig(name="mobile", driver="fcm", primary=True)
        assert cfg.primary is True

    def test_with_fcm_config(self) -> None:
        """Test NamedPushConfig with FCMDriverConfig."""
        fcm_cfg = FCMDriverConfig(server_key="server_key_123")
        cfg = NamedPushConfig(name="mobile", driver="fcm", primary=True, fcm=fcm_cfg)
        assert cfg.fcm is not None
        assert cfg.fcm.server_key.get_secret_value() == "server_key_123"


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_empty(self) -> None:
        """Test NotificationConfig with no backends."""
        cfg = NotificationConfig()
        assert cfg.sms_backends == []
        assert cfg.push_backends == []

    def test_multi_sms(self) -> None:
        """Test NotificationConfig with multiple SMS backends."""
        cfg = NotificationConfig(
            sms_backends=[
                NamedSMSConfig(name="alerts", primary=True, driver="twilio"),
                NamedSMSConfig(name="marketing", driver="twilio"),
            ]
        )
        assert len(cfg.sms_backends) == 2
        assert cfg.sms_backends[0].primary is True
        assert cfg.sms_backends[1].primary is False

    def test_multi_push(self) -> None:
        """Test NotificationConfig with multiple push backends."""
        cfg = NotificationConfig(
            push_backends=[
                NamedPushConfig(name="mobile", primary=True, driver="fcm"),
            ]
        )
        assert len(cfg.push_backends) == 1
        assert cfg.push_backends[0].primary is True

    def test_mixed_backends(self) -> None:
        """Test NotificationConfig with both SMS and push backends."""
        cfg = NotificationConfig(
            sms_backends=[
                NamedSMSConfig(name="alerts", primary=True, driver="twilio"),
            ],
            push_backends=[
                NamedPushConfig(name="mobile", primary=True, driver="fcm"),
            ],
        )
        assert len(cfg.sms_backends) == 1
        assert len(cfg.push_backends) == 1
