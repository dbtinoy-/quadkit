"""Tests for core scopes module in quadkit-contracts."""


import pytest
from quadkit.contracts.core.scopes import ServiceScope


class TestServiceScope:
    """Tests for ServiceScope enum."""

    def test_transient_value(self) -> None:
        """Test transient scope value."""
        assert ServiceScope.TRANSIENT.value == "transient"

    def test_singleton_value(self) -> None:
        """Test singleton scope value."""
        assert ServiceScope.SINGLETON.value == "singleton"

    def test_scoped_value(self) -> None:
        """Test scoped scope value."""
        assert ServiceScope.SCOPED.value == "scoped"

    def test_all_scopes_defined(self) -> None:
        """Test all scope types are defined."""
        scopes = list(ServiceScope)
        assert len(scopes) >= 3
        assert ServiceScope.TRANSIENT in scopes
        assert ServiceScope.SINGLETON in scopes
        assert ServiceScope.SCOPED in scopes