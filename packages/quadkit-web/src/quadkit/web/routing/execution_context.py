"""Web execution context implementation.

Provides the concrete ExecutionContextProtocol for HTTP requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web.protocols import ExecutionContextProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


class WebExecutionContext(ExecutionContextProtocol):
    """Concrete execution context for HTTP requests.

    Provides access to request metadata, handler information, and route details
    for use by interceptors, guards, and pipelines.
    """

    def __init__(
        self,
        request: Any,
        handler: Callable,
        controller_class: type | None = None,
        method_name: str | None = None,
        route_metadata: dict[str, Any] | None = None,
        container: Any = None,
    ):
        """Initialize the execution context.

        Args:
            request: The current HTTP request.
            handler: The handler function that will be called.
            controller_class: The controller class, if this is a controller method.
            method_name: The name of the method being called.
            route_metadata: Metadata about the route.
            container: Scoped DI container for the request.
        """
        self._request = request
        self._handler = handler
        self._controller_class = controller_class
        self._method_name = method_name
        self._route_metadata = route_metadata or {}
        self._container = container

    @property
    def request(self) -> Any:
        """The current HTTP request."""
        return self._request

    @property
    def handler(self) -> Callable:
        """The handler function that will be called."""
        return self._handler

    @property
    def controller_class(self) -> type | None:
        """The controller class, if this is a controller method."""
        return self._controller_class

    @property
    def method_name(self) -> str | None:
        """The name of the method being called."""
        return self._method_name

    @property
    def route_metadata(self) -> dict[str, Any]:
        """Metadata about the route."""
        return self._route_metadata

    @property
    def container(self) -> Any:
        """The scoped DI container for this request."""
        return self._container

    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom value from the context."""
        return self._route_metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a custom value on the context."""
        self._route_metadata[key] = value


__all__ = ["WebExecutionContext"]
