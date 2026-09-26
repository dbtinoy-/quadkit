import pytest
from quadkit.auth.authz.scopes import ScopeManager, OAuthScope

def test_scope_manager_permissions():
    manager = ScopeManager()
    
    assert manager.get_scope_permissions(OAuthScope.READ) == {"read"}
    assert manager.get_scope_permissions(OAuthScope.WRITE) == {"read", "write"}
    assert "admin" in manager.get_scope_permissions(OAuthScope.ADMIN)
    assert manager.get_scope_permissions("unknown") == set()

def test_get_scopes_for_permissions():
    manager = ScopeManager()
    
    # "admin" perm should require "admin" scope
    scopes = manager.get_scopes_for_permissions(["admin"])
    assert OAuthScope.ADMIN in scopes
    
    # "read" perm is contained in all scopes
    scopes = manager.get_scopes_for_permissions(["read"])
    assert OAuthScope.READ in scopes
    assert OAuthScope.WRITE in scopes
    assert OAuthScope.DELETE in scopes

def test_validate_scopes():
    manager = ScopeManager()
    requested = ["read", "write", "invalid"]
    allowed = ["read", "profile"]
    
    valid = manager.validate_scopes(requested, allowed)
    assert valid == ["read"]

def test_expand_scope_permissions():
    manager = ScopeManager()
    scopes = [OAuthScope.READ, OAuthScope.WRITE.value]
    perms = manager.expand_scope_permissions(scopes)
    assert perms == {"read", "write"}
