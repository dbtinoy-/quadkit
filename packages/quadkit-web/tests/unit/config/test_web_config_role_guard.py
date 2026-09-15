"""Unit tests for WebConfig.role_guard parsing and defaults."""

from __future__ import annotations

from quadkit.web.config import RoleGuardConfig, RoleGuardRuleConfig, WebConfig


class TestRoleGuardConfig:
    """Test the role guard configuration API."""

    def test_role_guard_defaults_to_no_rules(self) -> None:
        """A plain WebConfig has no role guard rules."""
        config = WebConfig()

        assert config.role_guard == RoleGuardConfig()
        assert config.role_guard.rules == []
        assert config.role_guard.enabled is False

    def test_role_guard_parses_rules(self) -> None:
        """Role rules parse into path + roles, preserving '/**' paths."""
        config = WebConfig(
            role_guard=RoleGuardConfig(
                rules=[
                    RoleGuardRuleConfig(path="/api/users", roles=["admin"]),
                    RoleGuardRuleConfig(
                        path="/api/admin/**", roles=["admin", "moderator"]
                    ),
                ]
            )
        )

        assert len(config.role_guard.rules) == 2

        first = config.role_guard.rules[0]
        assert first.path == "/api/users"
        assert first.roles == ["admin"]

        second = config.role_guard.rules[1]
        assert second.path == "/api/admin/**"
        assert second.roles == ["admin", "moderator"]
        assert config.role_guard.enabled is True

    def test_role_guard_rules_is_optional(self) -> None:
        """An empty RoleGuardConfig section yields no rules."""
        config = WebConfig(role_guard=RoleGuardConfig())

        assert config.role_guard.rules == []
        assert config.role_guard == RoleGuardConfig()
