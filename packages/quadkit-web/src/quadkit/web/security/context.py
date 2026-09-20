"""Security context for storing authentication state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.requests import Request


@dataclass
class SecurityContext:
    """
    Security context containing authentication and authorization info.

    Stored in request.state.security for access in guards and handlers.
    """

    user: Any | None = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user is not None

    def has_role(self, role: str) -> bool:
        """Check if user has specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        return permission in self.permissions

    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)

    def has_all_roles(self, *roles: str) -> bool:
        """Check if user has all of the specified roles."""
        return all(role in self.roles for role in roles)


def get_security_context(request: Request) -> SecurityContext:
    """
    Get or create security context from request state.

    Args:
        request: The HTTP request

    Returns:
        Security context instance
    """
    if not hasattr(request.state, "security"):
        request.state.security = SecurityContext()

    ctx: SecurityContext = request.state.security
    return ctx


__all__ = ["SecurityContext", "get_security_context"]
