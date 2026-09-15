"""Tests for config protocols."""

from __future__ import annotations

from quadkit.contracts.core.config import (
    ConfigIssue,
    ConfigProtocol,
    Environment,
)


class TestEnvironment:
    """Tests for Environment enum."""

    def test_all_environments(self) -> None:
        assert Environment.DEVELOPMENT == "development"
        assert Environment.STAGING == "staging"
        assert Environment.PRODUCTION == "production"
        assert Environment.TEST == "test"

    def test_is_string_enum(self) -> None:
        env = Environment.DEVELOPMENT
        assert isinstance(env, str)
        assert env == "development"


class TestConfigIssue:
    """Tests for ConfigIssue."""

    def test_create(self) -> None:
        issue = ConfigIssue(
            field="database.url",
            message="missing required field",
            severity="error",
            suggestion="Add database URL",
        )
        assert issue.field == "database.url"
        assert issue.message == "missing required field"
        assert issue.severity == "error"


class TestConfigProtocol:
    """Tests for ConfigProtocol."""

    def test_has_environment_property(self) -> None:
        assert hasattr(ConfigProtocol, "environment")

    def test_has_get_method(self) -> None:
        assert hasattr(ConfigProtocol, "get")

    def test_has_get_section_method(self) -> None:
        assert hasattr(ConfigProtocol, "get_section")

    def test_has_has_section_method(self) -> None:
        assert hasattr(ConfigProtocol, "has_section")
