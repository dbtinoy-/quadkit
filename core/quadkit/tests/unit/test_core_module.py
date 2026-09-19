"""Tests for CoreModule (kernel provider manifest) and StandardModule."""

from __future__ import annotations

from typing import Any

from quadkit.app.module import CoreModule, _instantiate_provider
from quadkit.config.di.provider import ConfigProvider
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.provider import Provider
from quadkit.identity.di.provider import IdentityProvider
from quadkit.logging.di.provider import LoggingProvider
from quadkit.observability.di.sub_providers.observability import ObservabilityProvider


class _StubProvider(Provider):
    name = "stub"

    async def boot(self, container: Any) -> None:  # noqa: ARG002
        return None

    async def dispose(self, container: Any) -> None:  # noqa: ARG002
        return None


class TestCoreModuleConfigure:
    def test_configure_returns_dynamic_module(self) -> None:
        dm = CoreModule.configure()
        assert isinstance(dm, DynamicModule)
        assert dm.is_global is True
        assert dm.module is CoreModule

    def test_providers_instantiated_in_order(self) -> None:
        dm = CoreModule.configure()
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        assert len(providers) == 6
        assert isinstance(providers[0], ConfigProvider)
        assert isinstance(providers[1], LoggingProvider)
        assert isinstance(providers[3], IdentityProvider)
        assert isinstance(providers[4], ObservabilityProvider)

    def test_exports_contain_core_types(self) -> None:
        dm = CoreModule.configure()
        export_names = {getattr(t, "__name__", str(t)) for t in dm.exports}
        assert "Application" in export_names
        assert "ConfigProtocol" in export_names
        assert "Context" in export_names

    def test_override_matching_provider(self) -> None:
        stub = _StubProvider()
        dm = CoreModule.configure(overrides={"config": stub})
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        config_providers = [p for p in providers if isinstance(p, ConfigProvider)]
        # The stub replaces the ConfigProvider — none left of that type.
        assert config_providers == []
        assert stub in providers

    def test_override_unmatched_name_appended(self) -> None:
        stub = _StubProvider()
        dm = CoreModule.configure(overrides={"my-extra": stub})
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        assert len(providers) == 7
        assert providers[-1] is stub

    def test_config_kwargs_forwarded(self) -> None:
        @DataclassConfig
        class MyConfig:
            pass

        dm = CoreModule.configure(config_class=MyConfig, env_prefix="QK_APP")
        config_provider = next(
            p for p in dm.providers if isinstance(p, ConfigProvider)
        )
        assert config_provider.config_class is MyConfig

    def test_multiple_overrides_preserve_order(self) -> None:
        stub_a = _StubProvider()
        stub_b = _StubProvider()
        stub_b.name = "stub-b"
        stub_c = _StubProvider()
        stub_c.name = "stub-c"
        dm = CoreModule.configure(
            overrides={"config": stub_a, "extra-2": stub_b, "extra-1": stub_c}
        )
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        assert providers[0] is stub_a  # override in the config slot
        assert providers[-2] is stub_b  # unmatched appended in dict order
        assert providers[-1] is stub_c
        assert len(providers) == 8  # 6 core (1 replaced) + 2 unmatched


# small helper to define a config dataclass without importing dataclasses twice
from dataclasses import dataclass as _dc  # noqa: E402


def DataclassConfig(cls: type) -> type:
    return _dc(init=False)(cls)


class TestBuildProviders:
    def test_build_providers_matches_configure(self) -> None:
        providers = CoreModule.build_providers()
        assert len(providers) == 6
        assert all(isinstance(p, Provider) for p in providers)

    def test_build_providers_with_overrides(self) -> None:
        stub = _StubProvider()
        providers = CoreModule.build_providers(overrides={"config": stub})
        assert stub in providers
        assert len(providers) == 6

    def test_build_providers_config_class(self) -> None:
        @DataclassConfig
        class Cfg:
            pass

        providers = CoreModule.build_providers(config_class=Cfg)
        config_provider = next(p for p in providers if isinstance(p, ConfigProvider))
        assert config_provider.config_class is Cfg


class TestInstantiateProvider:
    def test_config_provider_gets_config_kwargs(self) -> None:
        provider = _instantiate_provider(
            ConfigProvider,
            config_class=None,
            config_sources=None,
            env_prefix="QK",
        )
        assert isinstance(provider, ConfigProvider)
        assert provider.env_prefix == "QK"

    def test_other_providers_default_constructed(self) -> None:
        provider = _instantiate_provider(
            IdentityProvider,
            config_class=None,
            config_sources=None,
            env_prefix="",
        )
        assert isinstance(provider, IdentityProvider)


class TestModuleDecoration:
    def test_module_metadata(self) -> None:
        # The @module() decorator stores its metadata in __quadkit_module__.
        meta = CoreModule.__quadkit_module__
        assert meta.name == "CoreModule"
        assert len(meta.providers) == 6
        assert meta.providers[0] is ConfigProvider


from quadkit.app.standard import (  # noqa: E402
    _STANDARD_PROVIDERS,
    StandardModule,
)
from quadkit.concurrency.di.provider import ConcurrencyProvider  # noqa: E402
from quadkit.serialization.di.provider import SerializationProvider  # noqa: E402


class TestStandardModule:
    def test_providers_are_core_superset(self) -> None:
        names = [c.__name__ for c in _STANDARD_PROVIDERS]
        assert names == [
            "ConfigProvider",
            "LoggingProvider",
            "CoreInfrastructureProvider",
            "IdentityProvider",
            "ObservabilityProvider",
            "SerializationProvider",
            "ConcurrencyProvider",
            "DiProvider",
        ]

    def test_configure_returns_dynamic_module(self) -> None:
        dm = StandardModule.configure()
        assert isinstance(dm, DynamicModule)
        assert dm.is_global is True
        assert dm.module is StandardModule
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        assert len(providers) == 8
        assert isinstance(providers[5], SerializationProvider)
        assert isinstance(providers[6], ConcurrencyProvider)

    def test_exports_include_serialization(self) -> None:
        dm = StandardModule.configure()
        export_names = {getattr(t, "__name__", str(t)) for t in dm.exports}
        assert "JsonSerializerProtocol" in export_names
        assert "Application" in export_names  # inherited core exports

    def test_override_replaces_serialization_once(self) -> None:
        stub = _StubProvider()
        stub.name = "custom-serialization"
        dm = StandardModule.configure(overrides={"serialization": stub})
        providers = [p for p in dm.providers if isinstance(p, Provider)]
        assert len(providers) == 8  # 7 replaced-in-place + ... exactly 8 total
        assert stub in providers
        assert providers.count(stub) == 1  # the double-append bug regression
        assert all(not isinstance(p, SerializationProvider) for p in providers)

    def test_build_providers(self) -> None:
        providers = StandardModule.build_providers()
        assert len(providers) == 8
        assert all(isinstance(p, Provider) for p in providers)

    def test_module_metadata(self) -> None:
        meta = StandardModule.__quadkit_module__
        assert meta.name == "StandardModule"
        assert len(meta.providers) == 8
