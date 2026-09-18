"""Tests for provider protocols."""

from __future__ import annotations

from quadkit.contracts.core.provider import (
    Lifecycle,
    ProviderPriority,
    ProviderProtocol,
)


class TestProviderPriority:
    """Tests for ProviderPriority enum."""

    def test_all_priorities(self) -> None:
        assert ProviderPriority.CRITICAL == 0
        assert ProviderPriority.INFRASTRUCTURE == 10
        assert ProviderPriority.SECURITY == 20
        assert ProviderPriority.NORMAL == 30
        assert ProviderPriority.APPLICATION == 40
        assert ProviderPriority.DOMAIN == 50
        assert ProviderPriority.PRESENTATION == 80
        assert ProviderPriority.COMMS == 90
        assert ProviderPriority.LOW == 100

    def test_is_int_enum(self) -> None:
        priority = ProviderPriority.NORMAL
        assert isinstance(priority, int)
        assert priority == 30


class TestProviderProtocol:
    """Tests for ProviderProtocol."""

    def test_has_register_method(self) -> None:
        assert hasattr(ProviderProtocol, "register")

    def test_has_boot_method(self) -> None:
        assert hasattr(ProviderProtocol, "boot")

    def test_has_shutdown_method(self) -> None:
        assert hasattr(ProviderProtocol, "shutdown")

    def test_has_on_error_method(self) -> None:
        assert hasattr(ProviderProtocol, "on_error")


class TestLifecycle:
    """Tests for Lifecycle enum."""

    def test_all_stages(self) -> None:
        assert Lifecycle.REGISTER == "register"
        assert Lifecycle.STARTUP == "startup"
        assert Lifecycle.SHUTDOWN == "shutdown"
