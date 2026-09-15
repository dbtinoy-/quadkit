"""Tests for PluginEngineProvider boot integration."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.plugins import PluginDescriptor
from quadkit.di.provider import Provider
from quadkit.di.provider import ProviderPriority
from quadkit.plugins.engine import PluginEngineProvider


class _FakeProvider(Provider):
    name = "fake"

    def __init__(self) -> None:
        super().__init__()
        self.register_called = False
        self.boot_called = False
        self.shutdown_called = False

    async def register(self, container: Any) -> None:
        self.register_called = True
        container.registered.append(self.name)

    async def boot(self, container: Any) -> None:
        self.boot_called = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _FrameworkProvider(Provider):
    """A provider registered under EP_PROVIDERS with NO plugin descriptor."""

    name = "framework-provider"

    def __init__(self) -> None:
        super().__init__()
        self.register_called = False

    async def register(self, container: Any) -> None:
        self.register_called = True
        container.registered.append(self.name)


class _FakeRegistrar:
    def __init__(self) -> None:
        self.registered: list[str] = []


def _fake_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    providers: dict[str, type],
    descriptors: dict[str, PluginDescriptor] | None = None,
) -> None:
    class _FakeEntryPoint:
        def __init__(self, name: str, loaded: Any) -> None:
            self.name = name
            self._loaded = loaded

        def load(self) -> Any:
            return self._loaded

    descriptor_eps = [
        _FakeEntryPoint(name, descriptor)
        for name, descriptor in (descriptors or {}).items()
    ]
    provider_eps = [_FakeEntryPoint(name, cls) for name, cls in providers.items()]

    def _entry_points(*, group: str) -> list[Any]:
        if group == "quadkit.plugins":
            return descriptor_eps
        if group == "quadkit.providers":
            return provider_eps
        return []

    monkeypatch.setattr("quadkit.plugins.discovery._entry_points", _entry_points)


def _descriptor(name: str, provider_entry_point: str) -> PluginDescriptor:
    return PluginDescriptor(
        name=name,
        display_name=name,
        description="test descriptor",
        icon="puzzle",
        provider_entry_point=provider_entry_point,
    )


@pytest.mark.asyncio
async def test_engine_registers_enabled_providers(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _fake_entry_points(
        monkeypatch,
        providers={"fake": _FakeProvider},
        descriptors={
            "fake-plugin": _descriptor("fake-plugin", provider_entry_point="fake")
        },
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    registrar = _FakeRegistrar()
    await engine.register(registrar)
    assert registrar.registered == ["fake"]
    assert len(engine.discovered_providers) == 1


@pytest.mark.asyncio
async def test_engine_skips_disabled_providers(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _fake_entry_points(
        monkeypatch,
        providers={"fake": _FakeProvider},
        descriptors={
            "fake-plugin": _descriptor("fake-plugin", provider_entry_point="fake")
        },
    )
    from quadkit.plugins.state import save_disabled

    save_disabled({"fake"}, tmp_path / "plugins.json")
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    registrar = _FakeRegistrar()
    await engine.register(registrar)
    assert registrar.registered == []
    assert engine.discovered_providers == []


@pytest.mark.asyncio
async def test_engine_skips_framework_providers_without_descriptor(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """EP_PROVIDERS entries without a plugin descriptor are not plugins."""
    _fake_entry_points(
        monkeypatch,
        providers={"framework": _FrameworkProvider},
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    registrar = _FakeRegistrar()
    await engine.register(registrar)
    assert registrar.registered == []
    assert engine.discovered_providers == []


@pytest.mark.asyncio
async def test_engine_skips_framework_provider_even_when_mixed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Framework providers coexist with plugins without being registered."""
    _fake_entry_points(
        monkeypatch,
        providers={
            "fake": _FakeProvider,
            "framework": _FrameworkProvider,
        },
        descriptors={
            "fake-plugin": _descriptor("fake-plugin", provider_entry_point="fake")
        },
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    registrar = _FakeRegistrar()
    await engine.register(registrar)
    assert registrar.registered == ["fake"]
    assert len(engine.discovered_providers) == 1
    assert isinstance(engine.discovered_providers[0], _FakeProvider)


@pytest.mark.asyncio
async def test_engine_noop_when_no_plugin_descriptors(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _fake_entry_points(
        monkeypatch,
        providers={},
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    registrar = _FakeRegistrar()
    await engine.register(registrar)
    assert registrar.registered == []
    assert engine.discovered_providers == []


@pytest.mark.asyncio
async def test_engine_boots_and_shuts_down_discovered(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _fake_entry_points(
        monkeypatch,
        providers={"fake": _FakeProvider},
        descriptors={
            "fake-plugin": _descriptor("fake-plugin", provider_entry_point="fake")
        },
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    await engine.register(_FakeRegistrar())
    container: Any = object()
    await engine.boot(container)
    await engine.shutdown()
    provider = engine.discovered_providers[0]
    assert provider.boot_called and provider.shutdown_called


def test_engine_provider_metadata() -> None:
    engine = PluginEngineProvider()
    assert engine.name == "plugins"
    assert engine.priority == ProviderPriority.INFRASTRUCTURE


def test_plugins_module_configure_returns_provider(tmp_path) -> None:
    from quadkit.plugins.module import PluginsModule

    dynamic = PluginsModule.configure(state_path=tmp_path / "plugins.json")
    provider_classes = [p.__class__ for p in dynamic.providers]
    assert PluginEngineProvider in provider_classes


@pytest.mark.asyncio
async def test_engine_registers_via_shared_discovery_primitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """L1: the engine must reuse discover_providers, not reimplement the loop."""
    _fake_entry_points(
        monkeypatch,
        providers={"fake": _FakeProvider},
        descriptors={
            "fake-plugin": _descriptor("fake-plugin", provider_entry_point="fake")
        },
    )
    from quadkit.plugins import engine as engine_mod

    calls: list[set[str] | None] = []
    real = engine_mod.discover_providers

    def recorder(disabled: set[str] | None = None) -> list[Provider]:
        calls.append(disabled)
        return real(disabled=disabled)

    monkeypatch.setattr(engine_mod, "discover_providers", recorder)
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    await engine.register(_FakeRegistrar())
    assert calls == [set()]
    assert [p.name for p in engine.discovered_providers] == ["fake"]


@pytest.mark.asyncio
async def test_engine_excludes_plugin_with_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """L2: a plugin whose requires are unmet must not be registered."""
    rag = PluginDescriptor(
        name="rag-plugin",
        display_name="RAG",
        description="requires relay-gateway",
        icon="database",
        provider_entry_point="rag",
        requires=("relay-gateway",),
    )
    _fake_entry_points(
        monkeypatch,
        providers={"rag": _FakeProvider},
        descriptors={"rag-plugin": rag},
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    await engine.register(_FakeRegistrar())
    assert engine.discovered_providers == []


@pytest.mark.asyncio
async def test_engine_excludes_conflicting_plugin_keeps_other(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """L2: a plugin conflicting with an enabled one is excluded; the other stays."""
    a = _descriptor("a-plugin", provider_entry_point="a")
    b = PluginDescriptor(
        name="b-plugin",
        display_name="B",
        description="conflicts with a",
        icon="x",
        provider_entry_point="b",
        conflicts=("a",),
    )
    _fake_entry_points(
        monkeypatch,
        providers={"a": _FakeProvider, "b": _FakeProvider},
        descriptors={"a-plugin": a, "b-plugin": b},
    )
    engine = PluginEngineProvider(state_path=tmp_path / "plugins.json")
    await engine.register(_FakeRegistrar())
    assert len(engine.discovered_providers) == 1
