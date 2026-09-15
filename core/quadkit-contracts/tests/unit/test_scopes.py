"""Tests for contracts core scopes."""

import pytest

from quadkit.contracts.core.scopes import ServiceScope


class TestServiceScope:
    """Tests for ServiceScope enum."""

    def test_singleton_scope(self) -> None:
        """Test singleton scope value."""
        assert ServiceScope.SINGLETON.value == "singleton"

    def test_scoped_scope(self) -> None:
        """Test scoped scope value."""
        assert ServiceScope.SCOPED.value == "scoped"

    def test_transient_scope(self) -> None:
        """Test transient scope value."""
        assert ServiceScope.TRANSIENT.value == "transient"

    def test_all_scopes_defined(self) -> None:
        """Test all scopes are defined."""
        scopes = list(ServiceScope)
        assert len(scopes) == 3
        assert ServiceScope.SINGLETON in scopes
        assert ServiceScope.SCOPED in scopes
        assert ServiceScope.TRANSIENT in scopes

    def test_scope_is_string_enum(self) -> None:
        """Test that ServiceScope is a string enum."""
        # String enum allows comparison with string values
        assert ServiceScope.SINGLETON == "singleton"
        assert ServiceScope.SCOPED == "scoped"
        assert ServiceScope.TRANSIENT == "transient"
