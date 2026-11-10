"""Config-alignment tests for NotificationProvider."""

from __future__ import annotations

import pytest

from quadkit.notification.config import MailerConfig, NotificationConfig
from quadkit.notification.di.mailer_provider import MailerProvider
from quadkit.notification.di.provider import NotificationProvider


class _FakeRegistrar:
    def __init__(self) -> None:
        self.singletons: dict[type, object] = {}

    def singleton(
        self, cls: type, instance: object = None, factory: object = None
    ) -> None:
        self.singletons[cls] = factory if factory is not None else instance

    def transient(self, *args: object, **kwargs: object) -> None:
        pass


class TestConfigAlignment:
    def test_provider_declares_config_key_and_model(self) -> None:
        provider = NotificationProvider()
        assert provider.config_key == NotificationConfig.config_section
        assert provider.config_model is NotificationConfig

    @pytest.mark.asyncio
    async def test_injected_config_used_when_no_explicit(self) -> None:
        provider = NotificationProvider()
        provider.config = NotificationConfig(default_from="injected@example.com")
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[NotificationConfig] is provider.config

    @pytest.mark.asyncio
    async def test_explicit_config_wins_over_injected(self) -> None:
        explicit = NotificationConfig(enabled=False)
        provider = NotificationProvider(config=explicit)
        provider.config = NotificationConfig(default_from="injected@example.com")
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[NotificationConfig] is explicit

    @pytest.mark.asyncio
    async def test_default_config_binds_when_nothing_supplied(self) -> None:
        provider = NotificationProvider()
        container = _FakeRegistrar()

        await provider.register(container)

        assert isinstance(container.singletons[NotificationConfig], NotificationConfig)

    def test_mailer_provider_declares_config_key_and_model(self) -> None:
        provider = MailerProvider()
        assert provider.config_key == "mailer"
        assert provider.config_model is MailerConfig

    @pytest.mark.asyncio
    async def test_mailer_injected_config_used_when_no_explicit(self) -> None:
        provider = MailerProvider()
        provider.config = MailerConfig(console_fallback=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[MailerConfig] is provider.config

    @pytest.mark.asyncio
    async def test_mailer_explicit_config_wins_over_injected(self) -> None:
        explicit = MailerConfig(console_fallback=False)
        provider = MailerProvider(config=explicit)
        provider.config = MailerConfig()
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[MailerConfig] is explicit
