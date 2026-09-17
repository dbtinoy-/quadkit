"""Web middleware protocols for request/response processing guards."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ASGIMiddlewareProtocol(Protocol):
    """Protocol for ASGI-compatible middleware components.

    Implements the ASGI callable interface so middleware can be
    wrapped around any ASGI application.
    """

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """Handle an ASGI request.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        ...


__all__ = ["ASGIMiddlewareProtocol"]
