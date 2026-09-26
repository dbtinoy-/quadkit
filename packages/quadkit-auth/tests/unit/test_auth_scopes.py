"""Tests for auth scopes."""

import pytest

from quadkit.auth.authz.scopes import OAuthScope, ScopeManager


class TestOAuthScope:
    """Tests for OAuthScope enum."""

    def test_oauth_scope_values(self) -> None:
        """Test OAuthScope enum values."""
        assert OAuthScope.OPENID.value == "openid"
        assert OAuthScope.EMAIL.value == "email"
        assert OAuthScope.PROFILE.value == "profile"
        assert OAuthScope.READ.value == "read"
        assert OAuthScope.WRITE.value == "write"
        assert OAuthScope.DELETE.value == "delete"
        assert OAuthScope.ADMIN.value == "admin"

    def test_oauth_scope_members(self) -> None:
        """Test OAuthScope has expected members."""
        members = list(OAuthScope)
        assert len(members) >= 9


class TestScopeManager:
    """Tests for ScopeManager class."""

    def test_scope_manager_creation(self) -> None:
        """Test ScopeManager creation."""
        manager = ScopeManager()
        assert manager.scope_permissions is not None

    def test_get_scope_permissions_read(self) -> None:
        """Test get_scope_permissions for read scope."""
        manager = ScopeManager()
        perms = manager.get_scope_permissions("read")
        assert "read" in perms

    def test_get_scope_permissions_write(self) -> None:
        """Test get_scope_permissions for write scope."""
        manager = ScopeManager()
        perms = manager.get_scope_permissions("write")
        assert "read" in perms
        assert "write" in perms

    def test_get_scope_permissions_admin(self) -> None:
        """Test get_scope_permissions for admin scope."""
        manager = ScopeManager()
        perms = manager.get_scope_permissions("admin")
        assert "read" in perms
        assert "write" in perms
        assert "delete" in perms
        assert "admin" in perms

    def test_validate_scopes(self) -> None:
        """Test validate_scopes."""
        manager = ScopeManager()
        valid = manager.validate_scopes(
            requested_scopes=["read", "admin"],
            allowed_scopes=["read", "write"],
        )
        assert valid == ["read"]

    def test_expand_scope_permissions(self) -> None:
        """Test expand_scope_permissions."""
        manager = ScopeManager()
        perms = manager.expand_scope_permissions(["read"])
        assert "read" in perms
