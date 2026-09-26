"""Authorization (AuthZ) - Permissions and access control"""

from __future__ import annotations

from typing import Any

from quadkit.auth.authz.guards import (
    AuthorizationGuard,
    RouteGuard,
    optional_auth,
    require_auth,
    require_permissions,
    require_roles,
)
from quadkit.auth.authz.scopes import OAuthScope, ScopeManager
from quadkit.auth.authz.service import AuthorizationService


def __getattr__(name: str) -> Any:
    if name == "scope_manager":
        raise AttributeError(
            "scope_manager is now async. Use: await _get_scope_manager()",
        )
    raise AttributeError(f"module {__name__} has no attribute {name}")


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    "AuthorizationGuard",
    "AuthorizationService",
    "OAuthScope",
    "RouteGuard",
    "ScopeManager",
    "optional_auth",
    "require_auth",
    "require_permissions",
    "require_roles",
]
