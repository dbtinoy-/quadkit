"""Tests for quadkit.plugins.discovery.discover_providers."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.di.provider import Provider
from quadkit.plugins import discovery


class _FakeProvider(Provider):
    name = "fake"


class _BrokenCtorProvider(Provider):
    name = "broken"

    def __init__(self, required_arg: str) -> None:  # noqa: B027 — no default -> unconstructible
        super().__init__(name="broken")
        self.required_arg = required_arg


class _RaisingCtorProvider(Provider):
    """No-arg constructor that raises a non-TypeError (e.g. config validation)."""

    name = "raising"

    def __init__(self) -> None:
        super().__init__(name="raising")
        raise ValueError("default construction not possible")


class _FrameworkProvider(Provider):
    """EP_PROVIDERS registrant with no plugin descriptor — not a plugin."""

    name = "framework"


def _plugin_descriptor(provider_entry_point: str) -> PluginDescriptor:
    return PluginDescriptor(
        name=f"{provider_entry_point}-plugin",
        display_name=provider_entry_point,
        description="test",
        icon="puzzle",
        provider_entry_point=provider_entry_point,
    )


def _fake_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, type],
    descriptors: set[str] | dict[str, PluginDescriptor] | None = None,
) -> None:
    """Monkeypatch importlib.metadata.entry_points(group=...) for the given group.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        mapping: EP_PROVIDERS name -> provider class.
        descriptors: Set of provider_entry_point names to also declare
            under EP_PLUGINS, or a full plugin-descriptor mapping.
    """

    class _FakeEntryPoint:
        def __init__(self, name: str, loaded: Any) -> None:
            self.name = name
            self._loaded = loaded

        def load(self) -> Any:
            return self._loaded

    plugin_eps = []
    if isinstance(descriptors, dict):
        plugin_eps = [_FakeEntryPoint(name, d) for name, d in descriptors.items()]
    elif descriptors:
        plugin_eps = [
            _FakeEntryPoint(name, _plugin_descriptor(name)) for name in descriptors
        ]

    def _entry_points(*, group: str) -> list[Any]:
        if group == "quadkit.plugins":
            return plugin_eps
        if group != "quadkit.providers":
            return []
        return [_FakeEntryPoint(name, cls) for name, cls in mapping.items()]

    monkeypatch.setattr(discovery, "_entry_points", _entry_points)


def test_discover_providers_returns_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {"fake": _FakeProvider}, descriptors={"fake"})
    result = discovery.discover_providers()
    assert len(result) == 1
    assert isinstance(result[0], _FakeProvider)


def test_discover_providers_skips_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(monkeypatch, {"fake": _FakeProvider}, descriptors={"fake"})
    result = discovery.discover_providers(disabled={"fake"})
    assert result == []


def test_discover_providers_skips_unconstructible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(
        monkeypatch, {"broken": _BrokenCtorProvider}, descriptors={"broken"}
    )
    result = discovery.discover_providers()
    assert result == []


def test_discover_providers_skips_raising_ctor(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_entry_points(
        monkeypatch, {"raising": _RaisingCtorProvider}, descriptors={"raising"}
    )
    result = discovery.discover_providers()
    assert result == []


def test_discover_providers_empty_when_no_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_entry_points(monkeypatch, {})
    assert discovery.discover_providers() == []


def test_discover_providers_skips_framework_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EP_PROVIDERS registrants without a plugin descriptor are not plugins."""
    _fake_entry_points(monkeypatch, {"framework": _FrameworkProvider})
    result = discovery.discover_providers()
    assert result == []


def test_discover_providers_mixes_plugin_and_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only descriptor-referenced providers are returned."""
    _fake_entry_points(
        monkeypatch,
        {
            "fake": _FakeProvider,
            "framework": _FrameworkProvider,
        },
        descriptors={"fake"},
    )
    result = discovery.discover_providers()
    assert len(result) == 1
    assert isinstance(result[0], _FakeProvider)


from quadkit.contracts.plugins import PluginDescriptor

_SAMPLE_DESCRIPTOR = PluginDescriptor(
    name="relay-gateway",
    display_name="AI Gateway",
    description="AI relay/gateway capabilities.",
    icon="shuffle",
    provider_entry_point="relay-gateway",
)


def _fake_plugin_entry_points(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, PluginDescriptor]
) -> None:
    class _FakeEntryPoint:
        def __init__(self, name: str, descriptor: PluginDescriptor) -> None:
            self.name = name
            self._descriptor = descriptor

        def load(self) -> PluginDescriptor:
            return self._descriptor

    def _entry_points(*, group: str) -> list[Any]:
        if group != "quadkit.plugins":
            return []
        return [_FakeEntryPoint(name, d) for name, d in mapping.items()]

    monkeypatch.setattr(discovery, "_entry_points", _entry_points)


def test_discover_plugins_returns_descriptors(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_plugin_entry_points(monkeypatch, {"relay-gateway": _SAMPLE_DESCRIPTOR})
    result = discovery.discover_plugins()
    assert result == [_SAMPLE_DESCRIPTOR]


def test_discover_plugins_skips_non_descriptor(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeEntryPoint:
        name = "bad"

        def load(self) -> str:
            return "not a descriptor"

    def _entry_points(*, group: str) -> list[Any]:
        return [_FakeEntryPoint()] if group == "quadkit.plugins" else []

    monkeypatch.setattr(discovery, "_entry_points", _entry_points)
    assert discovery.discover_plugins() == []
