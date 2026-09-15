"""Web guard protocols.

Defines the core interface for guards that protect routes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.web.execution_context import ExecutionContextProtocol


@runtime_checkable
class GuardProtocol(Protocol):
    """Protocol for web guards.

    Guards determine whether a request should be handled by a specific route.
    They run before interceptors and handlers.
    """

    async def can_activate(self, context: ExecutionContextProtocol) -> bool:
        """Determine if the request can proceed.

        Args:
            context: The execution context for the request.

        Returns:
            True if the request is allowed, False otherwise.
        """
        ...

    async def handle_rejection(self, context: ExecutionContextProtocol) -> Any:
        """Handle guard rejection by returning a response.

        Args:
            context: The execution context for the request.

        Returns:
            A response object indicating the rejection.
        """
        ...


__all__ = ["GuardProtocol"]
