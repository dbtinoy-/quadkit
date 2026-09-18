"""Tests for DI protocols."""

from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerProtocol,
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)


class TestContainerRegistrarProtocol:
    """Tests for ContainerRegistrarProtocol."""

    def test_has_transient_method(self) -> None:
        assert hasattr(ContainerRegistrarProtocol, "transient")

    def test_has_singleton_method(self) -> None:
        assert hasattr(ContainerRegistrarProtocol, "singleton")

    def test_has_scoped_method(self) -> None:
        assert hasattr(ContainerRegistrarProtocol, "scoped")


class TestContainerResolverProtocol:
    """Tests for ContainerResolverProtocol."""

    def test_has_resolve_method(self) -> None:
        assert hasattr(ContainerResolverProtocol, "resolve")

    def test_has_bind_method(self) -> None:
        assert hasattr(ContainerResolverProtocol, "bind")


class TestContainerProtocol:
    """Tests for ContainerProtocol."""

    def test_has_register_method(self) -> None:
        assert hasattr(ContainerProtocol, "register")

    def test_has_resolve_method(self) -> None:
        assert hasattr(ContainerProtocol, "resolve")

    def test_has_has_method(self) -> None:
        assert hasattr(ContainerProtocol, "has")
