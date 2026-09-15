"""Execution context protocol for the web framework.

Kept in quadkit-contracts so that GuardProtocol (also in contracts) can
reference it without taking a dependency on quadkit-web.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class ExecutionContextProtocol(Protocol):
    """Provides metadata about the current request being processed.

    Used by interceptors and guards to access request information and make
    decisions about how to process the request/response.
    """

    @property
    def request(self) -> Any:
        """The current HTTP request."""
        ...

    @property
    def handler(self) -> Callable[..., Any]:
        """The handler function that will be called."""
        ...

    @property
    def controller_class(self) -> type | None:
        """The controller class, if this is a controller method."""
        ...

    @property
    def method_name(self) -> str | None:
        """The name of the method being called."""
        ...

    @property
    def route_metadata(self) -> dict[str, Any]:
        """Metadata about the route."""
        ...


__all__ = ["ExecutionContextProtocol"]
