"""OAuth2 scopes and scope management"""

from __future__ import annotations

from enum import StrEnum
import threading


class OAuthScope(StrEnum):
    """Standard OAuth2 scopes"""

    OPENID = "openid"
    EMAIL = "email"
    PROFILE = "profile"
    ADDRESS = "address"
    PHONE = "phone"

    # Custom scopes for applications
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class ScopeManager:
    """Manages OAuth2 scopes and their mappings.

    Thread-safe class for managing scope-to-permission mappings.

    .. note::
        Register as a singleton through ``AuthorizationProvider``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.scope_permissions: dict[str, set[str]] = {
            OAuthScope.READ: {"read"},
            OAuthScope.WRITE: {"read", "write"},
            OAuthScope.DELETE: {"read", "write", "delete"},
            OAuthScope.ADMIN: {"read", "write", "delete", "admin"},
        }

    def get_scope_permissions(self, scope: str) -> set[str]:
        """Get permissions associated with a scope."""
        with self._lock:
            return set(self.scope_permissions.get(scope, set()))

    def get_scopes_for_permissions(self, permissions: list[str]) -> set[str]:
        """Get minimum scopes required for permissions."""
        with self._lock:
            required_scopes = set()
            for perm in permissions:
                for scope, scope_perms in self.scope_permissions.items():
                    if perm in scope_perms:
                        required_scopes.add(scope)
            return required_scopes

    def validate_scopes(
        self,
        requested_scopes: list[str],
        allowed_scopes: list[str],
    ) -> list[str]:
        """Validate requested scopes against allowed scopes."""
        with self._lock:
            allowed_set = set(allowed_scopes)
            return list(
                filter(lambda scope: scope in allowed_set, requested_scopes),
            )

    def expand_scope_permissions(self, scopes: list[str]) -> set[str]:
        """Expand scopes to their associated permissions."""
        with self._lock:
            permissions = set()
            for scope in scopes:
                permissions.update(self.scope_permissions.get(scope, set()))
            return permissions


__all__ = [
    "OAuthScope",
    "ScopeManager",
]
