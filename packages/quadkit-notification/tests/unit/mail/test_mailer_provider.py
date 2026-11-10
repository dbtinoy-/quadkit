"""Tests for MailerProvider Named DI registration."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.notification.config import MailerConfig, NamedMailerConfig, SMTPDriverConfig
from quadkit.notification.di.mailer_provider import MailerProvider


class TestMailerProvider:
    @pytest.fixture
    def mock_container(self) -> MagicMock:
        container = MagicMock()
        container.singleton = MagicMock()
        return container

    @pytest.fixture
    def two_backend_config(self) -> MailerConfig:
        return MailerConfig(
            backends=[
                NamedMailerConfig(
                    name="transactional",
                    primary=True,
                    driver="smtp",
                    smtp=SMTPDriverConfig(host="smtp.example.com"),
                ),
                NamedMailerConfig(
                    name="internal",
                    driver="smtp",
                    smtp=SMTPDriverConfig(host="smtp.internal.com"),
                ),
            ]
        )

    @pytest.mark.asyncio
    async def test_registers_named_bindings(
        self, mock_container: MagicMock, two_backend_config: MailerConfig
    ) -> None:
        provider = MailerProvider(config=two_backend_config)
        await provider.register(mock_container)

        calls = mock_container.singleton.call_args_list
        named_calls = [c for c in calls if c.kwargs.get("name") is not None]
        names = {c.kwargs["name"] for c in named_calls}
        assert "transactional" in names
        assert "internal" in names

    @pytest.mark.asyncio
    async def test_primary_gets_unnamed_binding(
        self, mock_container: MagicMock, two_backend_config: MailerConfig
    ) -> None:
        provider = MailerProvider(config=two_backend_config)
        await provider.register(mock_container)

        calls = mock_container.singleton.call_args_list
        unnamed_calls = [
            c for c in calls
            if c.args and c.args[0] is MailerProtocol and c.kwargs.get("name") is None
        ]
        assert len(unnamed_calls) >= 1

    @pytest.mark.asyncio
    async def test_no_backends_skips_registration(
        self, mock_container: MagicMock
    ) -> None:
        provider = MailerProvider(config=MailerConfig())
        await provider.register(mock_container)
        calls = [c for c in mock_container.singleton.call_args_list if c.kwargs.get("name")]
        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_first_backend_is_primary_when_none_flagged(
        self, mock_container: MagicMock
    ) -> None:
        config = MailerConfig(
            backends=[
                NamedMailerConfig(name="first", driver="smtp"),
                NamedMailerConfig(name="second", driver="smtp"),
            ]
        )
        provider = MailerProvider(config=config)
        await provider.register(mock_container)

        calls = mock_container.singleton.call_args_list
        unnamed_calls = [
            c for c in calls
            if c.args and c.args[0] is MailerProtocol and c.kwargs.get("name") is None
        ]
        assert len(unnamed_calls) >= 1
