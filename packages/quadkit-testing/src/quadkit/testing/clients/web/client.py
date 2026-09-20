from __future__ import annotations

from typing import Any, Self, TypeVar, cast

from quadkit.app.base import Application

T = TypeVar("T")


def _starlette_test_client() -> Any:
    """Return Starlette's test client, imported on first use.

    Starlette's test client prefers the maintained ``httpx2`` package and
    warns when only the legacy ``httpx`` is installed; importing it at module
    scope would put that third-party warning on every consumer of this
    package, so the import happens when a client is built.

    Returns:
        The Starlette ``TestClient`` class.

    Raises:
        RuntimeError: When the optional test-client stack is not installed.
    """
    try:
        from starlette.testclient import TestClient
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "WebTestClient needs the test-client stack: install "
            "'quadkit-testing[web]' (starlette + httpx2)"
        ) from exc
    return TestClient


class TestResponse:
    """Enhanced response with assertion helpers.

    Wraps the standard Starlette/HTTPX response to provide fluent assertion
    methods for status codes, JSON structure, and headers.
    """

    def __init__(self, response: Any):
        self._response = response

    @property
    def status_code(self) -> int:
        """Get the HTTP status code."""
        return cast("int", self._response.status_code)

    @property
    def json(self) -> Any:
        """Get the JSON content."""
        return self._response.json()

    @property
    def text(self) -> str:
        """Get the response body as text."""
        return cast("str", self._response.text)

    @property
    def headers(self) -> dict[str, str]:
        """Get the response headers."""
        return dict(self._response.headers)

    def assert_status(self, expected: int) -> TestResponse:
        """Assert the response status code.

        Args:
            expected: The expected HTTP status code.

        Returns:
            self for chaining.
        """
        assert self._response.status_code == expected, (
            f"Expected status {expected}, got {self._response.status_code}"
        )
        return self

    def assert_json_path(self, path: str, expected: Any) -> TestResponse:
        """Assert a JSON path equals expected value.

        Args:
            path: Dot-separated path (e.g., 'data.user.id').
            expected: The expected value at that path.

        Returns:
            self for chaining.
        """
        data = self._response.json()

        # Navigate the path
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    current = None
            else:
                current = None

        assert current == expected, f"Expected {path}={expected}, got {current}"
        return self

    def assert_header(self, name: str, value: str) -> TestResponse:
        """Assert a header equals expected value.

        Args:
            name: Header name (case-insensitive).
            value: Expected header value.

        Returns:
            self for chaining.
        """
        assert self._response.headers.get(name.lower()) == value, (
            f"Expected header {name}={value}, got {self._response.headers.get(name.lower())}"
        )
        return self

    def assert_json(self, expected: dict[str, Any]) -> TestResponse:
        """Assert JSON matches expected dictionary.

        Args:
            expected: The expected JSON dictionary.

        Returns:
            self for chaining.
        """
        assert self._response.json() == expected
        return self

    def __await__(self) -> Any:
        """Allow await-ing a TestResponse in async tests (yields self)."""

        async def _identity() -> TestResponse:
            return self

        return _identity().__await__()


class WebTestClient:
    """Test client for testing web applications.

    Wraps Starlette's TestClient to provide a seamless testing experience
    for Quadkit web applications. It automatically extracts the underlying
    ASGI application from a Quadkit Application instance and provides
    assertion-aware TestResponse objects.

    .. note:: This class was renamed from ``TestClient`` to avoid pytest
        collecting it as a test class.
    """

    __test__ = False  # Mark as non-test class to avoid pytest collection

    def __init__(
        self,
        app: Any,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the WebTestClient.

        Args:
            app: A Quadkit Application, WebProvider, or raw ASGI application.
            base_url: The base URL for requests.
            raise_server_exceptions: Whether to raise exceptions that occur in the ASGI app.
            **kwargs: Additional arguments passed to the underlying Starlette TestClient.
        """
        self.app = app
        self.base_url = base_url.rstrip("/")
        self._user: Any = None
        self.headers: dict[str, str] = {}
        self._overrides: dict[type, Any] = {}

        # Extract the Starlette/ASGI app
        asgi_app = self._extract_asgi_app(app)

        # Initialize the underlying Starlette TestClient
        self._client = _starlette_test_client()(
            app=asgi_app,
            base_url=self.base_url,
            raise_server_exceptions=raise_server_exceptions,
            **kwargs,
        )

    def _extract_asgi_app(self, app: Any) -> Any:
        """Extract the ASGI application from the provided object."""
        # If it's a Quadkit Application
        if isinstance(app, Application):
            # Try to get the registered ASGI handler
            handler = getattr(app, "_asgi_handler", None)
            if handler is not None:
                return handler

            # If no handler, try to find the WebProvider
            from quadkit.contracts.web import WebProviderProtocol

            try:
                # Need to check container availability
                if hasattr(app, "container"):
                    web_provider = app.container.resolve_sync(WebProviderProtocol)  # type: ignore[type-abstract]
                    if hasattr(web_provider, "starlette") and web_provider.starlette:
                        return web_provider.starlette
            except Exception:  # noqa: BLE001 — fall through to the ASI-app fallback on any resolution error
                pass

        # If it's a WebProvider directly
        if hasattr(app, "starlette") and app.starlette is not None:
            return app.starlette

        # Fallback: assume it's already an ASGI app
        return app

    def as_user(self, user: Any) -> WebTestClient:
        """Simulate an authenticated user for subsequent requests.

        Args:
            user: The user object (must have an 'id' attribute or be convertible to str).

        Returns:
            self for chaining.
        """
        self._user = user
        return self

    def _prepare_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Add auth headers if user is set."""
        if self._user is not None:
            headers = kwargs.get("headers", {})
            if headers is None:
                headers = {}
            # Standard Quadkit test header for user simulation
            headers["X-User-ID"] = str(getattr(self._user, "id", self._user))
            kwargs["headers"] = headers
        return kwargs

    def get(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a GET request."""
        return TestResponse(self._client.get(url, **self._prepare_kwargs(kwargs)))

    def options(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform an OPTIONS request."""
        return TestResponse(self._client.options(url, **self._prepare_kwargs(kwargs)))

    def head(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a HEAD request."""
        return TestResponse(self._client.head(url, **self._prepare_kwargs(kwargs)))

    def post(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> TestResponse:
        """Perform a POST request."""
        return TestResponse(
            self._client.post(url, data=data, json=json, **self._prepare_kwargs(kwargs))
        )

    def put(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> TestResponse:
        """Perform a PUT request."""
        return TestResponse(
            self._client.put(url, data=data, json=json, **self._prepare_kwargs(kwargs))
        )

    def patch(
        self, url: str, data: Any = None, json: Any = None, **kwargs: Any
    ) -> TestResponse:
        """Perform a PATCH request."""
        return TestResponse(
            self._client.patch(
                url, data=data, json=json, **self._prepare_kwargs(kwargs)
            )
        )

    def delete(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a DELETE request."""
        return TestResponse(self._client.delete(url, **self._prepare_kwargs(kwargs)))

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> TestResponse:
        """Perform a generic HTTP request."""
        if headers is not None:
            kwargs["headers"] = headers
        return TestResponse(
            self._client.request(method, url, **self._prepare_kwargs(kwargs))
        )

    def websocket_connect(
        self, url: str, subprotocols: Any = None, **kwargs: Any
    ) -> Any:
        """Perform a WebSocket connection."""
        return self._client.websocket_connect(url, subprotocols=subprotocols, **kwargs)

    def __enter__(self) -> Self:
        self._client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._client.__exit__(*args)
