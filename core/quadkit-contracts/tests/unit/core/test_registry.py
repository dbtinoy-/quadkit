"""Tests for registry protocols."""

from __future__ import annotations

from quadkit.contracts.core.registry import RegistryProtocol


class TestRegistryProtocol:
    """Tests for RegistryProtocol."""

    def test_has_register_method(self) -> None:
        assert hasattr(RegistryProtocol, "register")

    def test_has_get_method(self) -> None:
        assert hasattr(RegistryProtocol, "get")

    def test_has_resolve_method(self) -> None:
        assert hasattr(RegistryProtocol, "resolve")

    def test_has_has_method(self) -> None:
        assert hasattr(RegistryProtocol, "has")

    def test_has_unregister_method(self) -> None:
        assert hasattr(RegistryProtocol, "unregister")

    def test_has_keys_method(self) -> None:
        assert hasattr(RegistryProtocol, "keys")

    def test_has_clear_method(self) -> None:
        assert hasattr(RegistryProtocol, "clear")
