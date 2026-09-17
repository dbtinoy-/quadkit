"""Database context protocol for cross-package tenant integration."""

from __future__ import annotations

from typing import Any, Protocol

if True:
    Scope = dict[str, Any]


class DatabaseContextProtocol(Protocol):
    """Protocol for database context that supports tenant isolation.

    This protocol allows packages like the optional provider to set tenant context
    without importing from the optional provider directly.

    The db_ctx is typically available in request scope at "state.db_ctx".
    """

    def set_tenant_from_scope(self, scope: Scope) -> Any | None:
        """Extract and set tenant from ASGI scope.

        Reads tenant from scope["state"]["tenant"] or scope["tenant"] and
        sets it in the database context.

        Args:
            scope: ASGI connection scope.

        Returns:
            A token that can be used to reset the context, or None if no tenant.
        """
        ...

    def reset_tenant(self, token: Any | None) -> None:
        """Reset the tenant context using a token from set_tenant_from_scope.

        Args:
            token: Token returned from set_tenant_from_scope.
        """
        ...


__all__ = ["DatabaseContextProtocol"]
