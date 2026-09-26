"""Session validation utilities for authentication middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.auth.models.user import User


class SessionValidator:
    """Handles session validation and authorization checks."""

    def __init__(self, config: Any, auth_provider: Any) -> None:
        """Initialize with configuration and auth provider.

        Args:
            config: AuthMiddlewareConfig
            auth_provider: AuthProviderProtocol instance
        """
        self.config = config
        self.auth_provider = auth_provider

    def check_authorization(self, user: User) -> bool:
        """Check if user is authorized based on roles/permissions.

        Args:
            user: Authenticated user

        Returns:
            True if authorized, False otherwise
        """
        if not user or not user.is_active:
            return False

        # Check required roles
        if self.config.roles_required and not self.auth_provider.has_any_role(
            user,
            self.config.roles_required,
        ):
            return False

        # Check required permissions
        return not (
            self.config.permissions_required
            and not self.auth_provider.has_any_permission(
                user, self.config.permissions_required
            )
        )

    def should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for this path.

        Args:
            path: Request path

        Returns:
            True if auth should be skipped
        """
        # Check exact path matches
        if path in self.config.exclude_paths:
            return True

        # Check path prefixes
        return any(path.startswith(prefix) for prefix in self.config.exclude_prefixes)


__all__ = ["SessionValidator"]
