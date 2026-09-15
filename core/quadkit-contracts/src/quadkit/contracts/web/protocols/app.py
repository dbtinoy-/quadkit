"""Web application, CRUD, and connection protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from quadkit.contracts.core.provider import ProviderProtocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.result import Result
    from quadkit.contracts.exceptions.domain import DomainError

T = TypeVar("T")

C = TypeVar("C")


@runtime_checkable
class WebProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for web providers that provide HTTP routing and middleware.

    Web providers are responsible for setting up HTTP servers, routing,
    middleware, and request/response handling.
    """


@runtime_checkable
class HTTPApplicationProtocol(Protocol):
    """Minimal protocol for an ASGI-compatible HTTP application.

    Extension packages that need to mount sub-applications (e.g.
    ``quadkit-graphql`` mounting a ``/graphql`` endpoint) must depend on
    this protocol — NOT on ``quadkit-web`` — to avoid cross-extension imports.
    The web provider implements this protocol; the container resolves it.
    """

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """ASGI callable entry-point.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive channel callable.
            send: ASGI send channel callable.
        """
        ...

    def mount(self, path: str, app: HTTPApplicationProtocol) -> None:
        """Mount a sub-application at the given path prefix.

        Args:
            path: URL path prefix (e.g. ``"/api/v2"``).
            app: The application to mount.
        """
        ...

    def add_route(
        self,
        path: str,
        handler: Any,
        methods: list[str] | None = None,
    ) -> None:
        """Register a route handler.

        Args:
            path: URL path pattern.
            handler: Callable (sync or async) that handles matched requests.
            methods: Allowed HTTP methods; ``None`` means all methods.
        """
        ...

    def add_middleware(self, middleware: Any) -> None:
        """Register a middleware layer.

        Middleware is applied in reverse registration order (last registered
        is the innermost layer).

        Args:
            middleware: A middleware class or instance.
        """
        ...


@runtime_checkable
class CRUDServiceProtocol(Protocol[T]):
    """Protocol for services that implement basic CRUD operations."""

    async def list_items(
        self, limit: int = 20, offset: int = 0, **filters: Any
    ) -> Result[list[T], DomainError]:
        """List items with pagination and filters."""
        ...

    async def get(self, item_id: Any) -> Result[T | None, DomainError]:
        """Get single item by ID."""
        ...

    async def create(self, data: dict[str, Any]) -> Result[T, DomainError]:
        """Create new item."""
        ...

    async def update(
        self, item_id: Any, data: dict[str, Any]
    ) -> Result[T | None, DomainError]:
        """Update existing item."""
        ...

    async def delete(self, item_id: Any) -> Result[bool, DomainError]:
        """Delete item."""
        ...


@runtime_checkable
class ConnectionManagerProtocol(Protocol[C]):  # type: ignore[misc]
    """Protocol for connection managers that track and broadcast to clients.

    Both WebSocket and SSE handlers manage connections; this protocol
    captures the shared surface so higher-level code can depend on the
    abstraction rather than a concrete transport.
    """

    async def add(self, connection: C) -> None:
        """Register a new connection."""
        ...

    async def remove(self, connection: C) -> None:
        """Unregister a connection."""
        ...

    async def broadcast(self, message: Any, exclude: C | None = None) -> None:
        """Send a message to all tracked connections."""
        ...

    @property
    def count(self) -> int:
        """Return the number of active connections."""
        ...


@runtime_checkable
class WebContributorProtocol(Protocol):
    """Protocol for packages that contribute controllers and middleware.

    Extension packages can also mount sub-applications via the mount_to_app hook.

    Extension packages can implement this protocol to register their HTTP
    controllers and middleware components with the web provider via
    entry-point discovery. This allows packages like ``quadkit-graphql``
    and ``quadkit-admin`` to expose web routes without requiring the
    web provider to explicitly import them.

    Example:
        ```python
        class GraphQLWebContributor:
            @property
            def contributor_id(self) -> str:
                return "graphql"

            def get_controllers(self) -> list[type]:
                return [GraphQLController]

            def get_middleware(self) -> list[type]:
                return []

            async def mount_to_app(
                self, app: HTTPApplicationProtocol, container: object
            ) -> None:
                pass  # No-op for controller-only contributors
        ```
    """

    @property
    def contributor_id(self) -> str:
        """Unique contributor identifier such as ``graphql`` or ``admin``.

        Returns:
            A string identifier for this contributor, used for tracking
            and debugging. Must be unique across all registered contributors.
        """
        ...

    def get_controllers(self) -> list[type[Any]]:
        """Return controller classes contributed by the package.

        Returns:
            List of controller classes to register with the web provider.
            Each class should implement the controller contract with
            route definitions.
        """
        ...

    def get_middleware(self) -> list[type[Any]]:
        """Return middleware classes contributed by the package.

        Returns:
            List of middleware classes to register with the web provider.
            Middleware is applied in registration order.
        """
        ...

    async def mount_to_app(self, app: Any, container: object) -> None:
        """Mount sub-applications or additional routes to the web app.

        Called during route setup phase after metrics and debug routes
        but before static files and controller discovery.

        Args:
            app: The ASGI application (typically Starlette) to mount routes on.
            container: The DI container for resolving dependencies.

        Note:
            Controller-only contributors should implement this as a no-op.
        """
        ...


@runtime_checkable
class BackgroundTaskRunnerProtocol(Protocol):
    """Protocol for in-process background task execution.

    Background tasks run after a response is sent to the client. This
    protocol models post-response callable execution inside the web layer.
    Durable job submission belongs to the task subsystem via
    ``TaskProviderProtocol`` / ``TaskQueueProtocol`` rather than this web
    background-runner contract.
    """

    def add_task(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Add a task to run in the background.

        Args:
            func: Async or sync callable to execute.
            *args: Positional arguments for the callable.
            **kwargs: Keyword arguments for the callable.
        """
        ...


@runtime_checkable
class CSRFProtectionProtocol(Protocol):
    """Protocol for CSRF (Cross-Site Request Forgery) protection.

    Validates that state-modifying requests (POST, PUT, PATCH, DELETE)
    include a valid CSRF token that matches the session cookie.

    This is essential for browser-based applications using session cookies.
    """

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token for a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            CSRF token string.
        """
        ...

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token against a session.

        Args:
            token: CSRF token from request.
            session_id: Session identifier.

        Returns:
            True if token is valid for the session.
        """
        ...

    def get_cookie_name(self) -> str:
        """Get the name of the CSRF cookie.

        Returns:
            Cookie name (default: "csrf_token").
        """
        ...

    def get_header_name(self) -> str:
        """Get the name of the CSRF header.

        Returns:
            Header name (default: "X-CSRF-Token").
        """
        ...
