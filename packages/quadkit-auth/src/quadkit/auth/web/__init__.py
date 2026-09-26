"""Web - Web framework integration and middleware"""

from __future__ import annotations

from quadkit.auth.web.guards import (
    AdminGuard,
    AuthGuard,
    CompositeGuard,
    GuardContext,
    GuardProtocol,
    PermissionGuard,
    RoleGuard,
    UserGuard,
    require_admin,
    require_auth,
    require_permission,
    require_role,
    use_guards,
)
from quadkit.auth.web.middleware.auth import (
    AuthMiddleware,
    AuthMiddlewareConfig,
    AuthRouter,
    optional_auth,
    require_permissions,
    require_roles,
)
from quadkit.auth.web.middleware.throttle import (
    RateLimitMiddleware,
)

__all__ = [
    "AdminGuard",
    "AuthGuard",
    # Middleware
    "AuthMiddleware",
    "AuthMiddlewareConfig",
    "AuthRouter",
    "CompositeGuard",
    "GuardContext",
    # Guards
    "GuardProtocol",
    "PermissionGuard",
    "RateLimitMiddleware",
    "RoleGuard",
    "UserGuard",
    "optional_auth",
    "require_admin",
    "require_auth",
    "require_permission",
    "require_permissions",
    "require_role",
    "require_roles",
    "use_guards",
]
