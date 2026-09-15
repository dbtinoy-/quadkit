"""Service mesh protocols.

Protocols for service discovery, load balancing, and communication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.web.http_types import ServiceInfo as ServiceInfo

if TYPE_CHECKING:
    from quadkit.contracts.web.http_models import HttpResponse


@runtime_checkable
class ServiceMeshRegistryProtocol(Protocol):
    """Protocol for service registry implementations.

    The service registry manages service instance registration
    and discovery.

    Example:
        ```python
        class ConsulRegistry:
            async def register(self, service: ServiceInfo) -> None:
                await self._client.agent.service.register(
                    name=service.name,
                    address=service.host,
                    port=service.port,
                )
        ```
    """

    async def register(self, service: ServiceInfo) -> None:
        """Register a service instance.

        Args:
            service: ServiceInfo to register.
        """
        ...

    async def deregister(self, service_name: str, host: str, port: int) -> None:
        """Deregister a service instance.

        Args:
            service_name: Name of the service.
            host: Service host.
            port: Service port.
        """
        ...

    async def discover(self, service_name: str) -> list[ServiceInfo]:
        """Discover all instances of a service.

        Args:
            service_name: Name of the service.

        Returns:
            List of ServiceInfo instances.
        """
        ...

    async def get_service(
        self,
        service_name: str,
        host: str,
        port: int,
    ) -> ServiceInfo | None:
        """Get a specific service instance.

        Args:
            service_name: Name of the service.
            host: Service host.
            port: Service port.

        Returns:
            ServiceInfo if found, None otherwise.
        """
        ...

    async def list_services(self) -> list[str]:
        """List all registered service names.

        Returns:
            List of service names.
        """
        ...


@runtime_checkable
class SelectorProtocol(Protocol):
    """Protocol for load balancing selectors.

    Selectors choose which service instance to route to.
    """

    async def select(self, instances: list[ServiceInfo]) -> ServiceInfo | None:
        """Select an instance from the available instances.

        Args:
            instances: List of available service instances.

        Returns:
            Selected instance or None.
        """
        ...


@runtime_checkable
class HTTPSessionProtocol(Protocol):
    """Protocol for underlying HTTP session implementations.

    This allows the HTTPClient to be backend-agnostic, enabling easier
    testing and support for different HTTP libraries.
    """

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform an HTTP request and return a raw response object."""
        ...

    async def close(self) -> None:
        """Close the session and release resources."""
        ...


@runtime_checkable
class HTTPClientProtocol(Protocol):
    """Protocol for HTTP client implementations."""

    async def start(self) -> None:
        """Start the HTTP client and its underlying connection pool."""
        ...

    async def stop(self) -> None:
        """Stop the HTTP client and release all connection resources."""
        ...

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        """Perform an arbitrary HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, …).
            url: Request URL.
            **kwargs: Additional options (headers, data, json, params, …).

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform GET request.

        Args:
            url: Request URL.
            **kwargs: Additional options.

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform POST request.

        Args:
            url: Request URL.
            **kwargs: Additional options (e.g. ``json=``, ``data=``).

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform PUT request.

        Args:
            url: Request URL.
            **kwargs: Additional options.

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform DELETE request.

        Args:
            url: Request URL.
            **kwargs: Additional options.

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform PATCH request.

        Args:
            url: Request URL.
            **kwargs: Additional options.

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...

    async def head(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform HEAD request.

        Args:
            url: Request URL.
            **kwargs: Additional options.

        Returns:
            Framework-owned :class:`HttpResponse`.
        """
        ...


@runtime_checkable
class InterceptorProtocol(Protocol):
    """Protocol for request/response interceptors.

    Interceptors are applied to every request/response cycle in
    :class:`~quadkit.http.HTTPClient`.  Implementations receive typed
    ``RequestContext`` objects and may modify them before the request is
    dispatched, or inspect / annotate the raw response after it arrives.

    Example:
        class LoggingInterceptor:
            async def intercept_request(self, context: Any) -> Any:
                logger.info("outbound_request", method=context.method, url=context.url)
                return context

            async def intercept_response(self, response: Any) -> Any:
                logger.info("inbound_response", status=response.status)
                return response
    """

    async def intercept_request(self, context: Any) -> Any:
        """Called before a request is dispatched.

        Args:
            context: :class:`~quadkit.http.RequestContext` for the outbound
                request.  Implementations may mutate and return it.

        Returns:
            The (possibly modified) request context.
        """
        ...

    async def intercept_response(self, response: Any) -> Any:
        """Called after a response is received from the server.

        Args:
            response: Raw response object from the underlying HTTP library.
                Implementations may annotate or replace it.

        Returns:
            The (possibly modified) response.
        """
        ...


@runtime_checkable
class InterceptorChainProtocol(Protocol):
    """Protocol for interceptor chain management.

    Manages a collection of interceptors and orchestrates their execution
    in sequence. Each interceptor in the chain processes the request/response
    before passing control to the next interceptor.

    Example:
        ```python
        class InterceptorChain:
            def __init__(self, interceptors: list[InterceptorProtocol]):
                self._interceptors = interceptors

            async def execute_request(self, context: Any) -> Any:
                for interceptor in self._interceptors:
                    context = await interceptor.intercept_request(context)
                return context

            async def execute_response(self, response: Any) -> Any:
                for interceptor in reversed(self._interceptors):
                    response = await interceptor.intercept_response(response)
                return response
        ```
    """

    def add_interceptor(self, interceptor: InterceptorProtocol) -> None:
        """Add an interceptor to the chain.

        Args:
            interceptor: The interceptor to add.
        """
        ...

    def remove_interceptor(self, interceptor: InterceptorProtocol) -> None:
        """Remove an interceptor from the chain.

        Args:
            interceptor: The interceptor to remove.
        """
        ...

    async def process_request(self, context: Any) -> Any:
        """Process request through the interceptor chain.

        Args:
            context: Request context to process.

        Returns:
            Modified request context after all interceptors.
        """
        ...

    async def process_response(self, response: Any) -> Any:
        """Process response through the interceptor chain.

        Args:
            response: Response to process.

        Returns:
            Modified response after all interceptors.
        """
        ...


@runtime_checkable
class ConnectMetricsCollectorProtocol(Protocol):
    """Protocol for service metrics collection."""

    def record_request(
        self,
        service: str,
        method: str,
        duration: float,
        status: int,
    ) -> None:
        """Record a request metric."""
        ...

    def get_metrics(self, service: str) -> dict[str, Any]:
        """Get metrics for a service."""
        ...


@runtime_checkable
class WebSocketProtocol(Protocol):
    """Framework-agnostic WebSocket connection contract.

    Abstracts over concrete WebSocket objects (Starlette, AIOHTTP, …) so
    the GraphQL subscription transport layer stays decoupled from the
    underlying web framework.
    """

    async def accept(
        self,
        subprotocol: str | None = None,
    ) -> None:
        """Accept the WebSocket upgrade handshake.

        Args:
            subprotocol: Optional WebSocket sub-protocol to negotiate
                (e.g. ``"graphql-transport-ws"``).
        """
        ...

    async def receive_text(self) -> str:
        """Receive the next text frame from the client.

        Returns:
            Raw text payload of the received frame.
        """
        ...

    async def receive_json(self) -> Any:
        """Receive the next frame and deserialise it as JSON.

        Returns:
            Deserialised JSON value.
        """
        ...

    async def send_text(self, data: str) -> None:
        """Send a text frame to the client.

        Args:
            data: Text payload to send.
        """
        ...

    async def send_json(self, data: Any) -> None:
        """Serialise *data* as JSON and send it to the client.

        Args:
            data: Value to serialise and send.
        """
        ...

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the WebSocket connection.

        Args:
            code: WebSocket close status code (default 1000 = normal closure).
            reason: Human-readable close reason.
        """
        ...


__all__ = [
    "ConnectMetricsCollectorProtocol",
    "HTTPClientProtocol",
    "HTTPSessionProtocol",
    "InterceptorChainProtocol",
    "InterceptorProtocol",
    "SelectorProtocol",
    "ServiceInfo",
    "ServiceMeshRegistryProtocol",
    "WebSocketProtocol",
]
