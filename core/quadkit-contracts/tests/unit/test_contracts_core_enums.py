"""Tests for additional contracts enums."""

import pytest

from quadkit.contracts.core.config import Environment
from quadkit.contracts.core.provider import Lifecycle


class TestEnvironment:
    """Tests for Environment enum."""

    def test_environment_values(self) -> None:
        """Test Environment enum values."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TEST.value == "test"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_members(self) -> None:
        """Test Environment has expected members."""
        members = list(Environment)
        assert len(members) == 4


class TestLifecycle:
    """Tests for Lifecycle enum."""

    def test_lifecycle_values(self) -> None:
        """Test Lifecycle enum values."""
        assert Lifecycle.REGISTER.value == "register"
        assert Lifecycle.STARTUP.value == "startup"
        assert Lifecycle.SHUTDOWN.value == "shutdown"

    def test_lifecycle_members(self) -> None:
        """Test Lifecycle has expected members."""
        members = list(Lifecycle)
        assert len(members) == 3