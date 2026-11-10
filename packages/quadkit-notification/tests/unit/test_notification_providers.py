"""Tests for MailerProvider, InboxProvider, and additional NotificationProvider scenarios."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.contracts.notification.inbox import InboxStoreProtocol
from quadkit.notification.config import (
    FCMDriverConfig,
    MailerConfig,
    NamedMailerConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    SendGridDriverConfig,
    TwilioDriverConfig,
)
from quadkit.notification.di.inbox_provider import InboxProvider
from quadkit.notification.di.mailer_provider import MailerProvider
from quadkit.notification.di.provider import NotificationProvider


class TestMailerProvider:
    @pytest.fixture
    def mock_container(self) -> MagicMock:
        container = MagicMock()
        container.singleton = MagicMock()
        return container

    @pytest.fixture
    def smtp_config(self) -> MailerConfig:
        return MailerConfig(
            backends=[
                NamedMailerConfig(
                    name="alerts",
                    primary=True,
                    driver="smtp",
                    smtp={"host": "smtp.example.com", "port": 587},
                    from_email="alerts@example.com",
                )
            ]
        )

    @pytest.fixture
    def sendgrid_config(self) -> MailerConfig:
        return MailerConfig(
            backends=[
                NamedMailerConfig(
                    name="sendgrid",
                    primary=True,
                    driver="sendgrid",
                    sendgrid=SendGridDriverConfig(api_key="SG.test"),
                    from_email="noreply@example.com",
                )
            ]
        )

    @pytest.fixture
    def multi_config(self) -> MailerConfig:
        return MailerConfig(
            backends=[
                NamedMailerConfig(
                    name="smtp",
                    primary=True,
                    driver="smtp",
                    smtp={"host": "smtp.example.com", "port": 587},
                    from_email="alerts@example.com",
                ),
                NamedMailerConfig(
                    name="sendgrid",
                    driver="sendgrid",
                    sendgrid=SendGridDriverConfig(api_key="SG.test"),
                    from_email="noreply@example.com",
                ),
            ]
        )

    @pytest.mark.asyncio
    async def test_registers_smtp_binding(self, mock_container, smtp_config) -> None:
        provider = MailerProvider(config=smtp_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        smtp_registered = [c for c in calls if MailerProtocol in c.args]
        assert len(smtp_registered) >= 1

    @pytest.mark.asyncio
    async def test_registers_sendgrid_binding(self, mock_container, sendgrid_config) -> None:
        provider = MailerProvider(config=sendgrid_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        sg_registered = [
            c for c in calls if c.kwargs.get("name") == "sendgrid"
        ]
        assert len(sg_registered) == 1

    @pytest.mark.asyncio
    async def test_registers_primary_unnamed(self, mock_container, multi_config) -> None:
        provider = MailerProvider(config=multi_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        unnamed = [c for c in calls if c.args and MailerProtocol in c.args and not c.kwargs.get("name")]
        assert len(unnamed) >= 1

    @pytest.mark.asyncio
    async def test_registers_named_bindings(self, mock_container, multi_config) -> None:
        provider = MailerProvider(config=multi_config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        named = [c for c in calls if c.kwargs.get("name") in ("smtp", "sendgrid")]
        assert len(named) == 2

    @pytest.mark.asyncio
    async def test_empty_config_health_healthy(self) -> None:
        provider = MailerProvider(config=MailerConfig())
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "mailer"

    @pytest.mark.asyncio
    async def test_boot_is_noop(self, mock_container, smtp_config) -> None:
        provider = MailerProvider(config=smtp_config)
        await provider.register(mock_container)
        await provider.boot(mock_container)

    @pytest.mark.asyncio
    async def test_shutdown_clears_mailers(self, smtp_config) -> None:
        provider = MailerProvider(config=smtp_config)
        mock_container = MagicMock()
        mock_container.singleton = MagicMock()
        await provider.register(mock_container)
        await provider.shutdown()
        assert len(provider._mailers) == 0


class TestInboxProvider:
    @pytest.fixture
    def mock_container(self) -> MagicMock:
        container = MagicMock()
        container.singleton = MagicMock()
        container.resolve = AsyncMock()
        return container

    @pytest.mark.asyncio
    async def test_registers_store_and_service(self, mock_container) -> None:
        provider = InboxProvider()
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        assert any(InboxStoreProtocol in c.args for c in calls)

    @pytest.mark.asyncio
    async def test_boot_resolves_store(self, mock_container) -> None:
        provider = InboxProvider()
        await provider.register(mock_container)
        await provider.boot(mock_container)
        mock_container.resolve.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_clears_store(self) -> None:
        provider = InboxProvider()
        await provider.shutdown()
        assert provider._store is None

    @pytest.mark.asyncio
    async def test_health_check_degraded_before_boot(self) -> None:
        provider = InboxProvider()
        result = await provider.health_check()
        assert result.status == HealthStatus.DEGRADED
        assert result.component == "inbox"

    @pytest.mark.asyncio
    async def test_health_check_after_boot(self, mock_container) -> None:
        provider = InboxProvider()
        await provider.register(mock_container)
        mock_store = MagicMock()
        mock_store.health_check = AsyncMock(
            return_value=MagicMock(
                status=HealthStatus.HEALTHY,
                message="ok",
            )
        )
        mock_container.resolve = AsyncMock(return_value=mock_store)
        await provider.boot(mock_container)
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY


class TestNotificationProviderAdditional:
    @pytest.fixture
    def mock_container(self) -> MagicMock:
        container = MagicMock()
        container.singleton = MagicMock()
        return container

    @pytest.mark.asyncio
    async def test_multiple_sms_backends_primary_first(self, mock_container) -> None:
        config = NotificationConfig(
            sms_backends=[
                NamedSMSConfig(
                    name="twilio1",
                    driver="twilio",
                    twilio=TwilioDriverConfig(
                        account_sid="AC1",
                        auth_token="token1",
                        from_number="+15550000001",
                    ),
                ),
                NamedSMSConfig(
                    name="twilio2",
                    primary=True,
                    driver="twilio",
                    twilio=TwilioDriverConfig(
                        account_sid="AC2",
                        auth_token="token2",
                        from_number="+15550000002",
                    ),
                ),
            ]
        )
        provider = NotificationProvider(config=config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        unnamed = [c for c in calls if c.args[0].__name__ in ("SMSChannelProtocol", "PushChannelProtocol") and not c.kwargs.get("name")]
        assert len(unnamed) >= 1

    @pytest.mark.asyncio
    async def test_multiple_push_backends(self, mock_container) -> None:
        config = NotificationConfig(
            push_backends=[
                NamedPushConfig(
                    name="fcm",
                    driver="fcm",
                    fcm=FCMDriverConfig(server_key="fcm-key"),
                ),
                NamedPushConfig(
                    name="apns",
                    driver="apns",
                    apns={"team_id": "T123", "key_id": "K456", "apns_auth_key": "key", "bundle_id": "com.app"},
                ),
            ]
        )
        provider = NotificationProvider(config=config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        named_push = [c for c in calls if c.kwargs.get("name") in ("fcm", "apns")]
        assert len(named_push) == 2

    @pytest.mark.asyncio
    async def test_sms_primary_false_when_other_is_primary(self, mock_container) -> None:
        config = NotificationConfig(
            sms_backends=[
                NamedSMSConfig(
                    name="twilio1",
                    primary=False,
                    driver="twilio",
                    twilio=TwilioDriverConfig(
                        account_sid="AC1",
                        auth_token="token1",
                        from_number="+15550000001",
                    ),
                ),
                NamedSMSConfig(
                    name="twilio2",
                    primary=True,
                    driver="twilio",
                    twilio=TwilioDriverConfig(
                        account_sid="AC2",
                        auth_token="token2",
                        from_number="+15550000002",
                    ),
                ),
            ]
        )
        provider = NotificationProvider(config=config)
        await provider.register(mock_container)
        calls = mock_container.singleton.call_args_list
        unnamed = [c for c in calls if c.args[0].__name__ == "SMSChannelProtocol" and not c.kwargs.get("name")]
        assert len(unnamed) == 1

    @pytest.mark.asyncio
    async def test_health_check_empty_returns_healthy(self) -> None:
        provider = NotificationProvider(config=NotificationConfig())
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.details == {"backends": []}


__all__ = ["TestMailerProvider", "TestInboxProvider", "TestNotificationProviderAdditional"]