"""Config-alignment tests for DatabaseProvider (sql)."""

from __future__ import annotations

import pytest

from quadkit.sql.config import DatabaseConfig
from quadkit.sql.di.provider import DatabaseProvider


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
        provider = DatabaseProvider()
        assert provider.config_key == DatabaseConfig.config_section
        assert provider.config_model is DatabaseConfig

    @pytest.mark.asyncio
    async def test_injected_config_used_when_no_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = DatabaseProvider()
        provider.config = DatabaseConfig(url="sqlite:///injected.db")
        captured: dict[str, object] = {}

        async def fake_register_single(
            container: object, config: object
        ) -> None:
            captured["config"] = config

        monkeypatch.setattr(provider, "_register_single_backend", fake_register_single)

        await provider.register(_FakeRegistrar())

        assert captured["config"] is provider.config

    @pytest.mark.asyncio
    async def test_explicit_config_wins_over_injected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        explicit = DatabaseConfig(url="sqlite:///explicit.db")
        provider = DatabaseProvider(config=explicit)
        provider.config = DatabaseConfig(url="sqlite:///injected.db")
        captured: dict[str, object] = {}

        async def fake_register_single(
            container: object, config: object
        ) -> None:
            captured["config"] = config

        monkeypatch.setattr(provider, "_register_single_backend", fake_register_single)

        await provider.register(_FakeRegistrar())

        assert captured["config"] is explicit

    @pytest.mark.asyncio
    async def test_default_config_used_when_nothing_supplied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = DatabaseProvider()
        captured: dict[str, object] = {}

        async def fake_register_single(
            container: object, config: object
        ) -> None:
            captured["config"] = config

        monkeypatch.setattr(provider, "_register_single_backend", fake_register_single)

        await provider.register(_FakeRegistrar())

        assert isinstance(captured["config"], DatabaseConfig)