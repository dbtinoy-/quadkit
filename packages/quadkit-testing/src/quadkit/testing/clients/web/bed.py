from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from quadkit.testing.clients.web.client import TestResponse, WebTestClient
from quadkit.testing.fixtures.bed import TestEnvironment

if TYPE_CHECKING:
    import types

    from quadkit.app.base import Application
    from quadkit.web.di.provider import WebProvider


class WebTestBed(TestEnvironment):
    """TestBed specialized for web applications.

    Extends :class:`~quadkit.testing.fixtures.bed.TestEnvironment` to add
    web-specific functionality. Accepts a `WebProvider` or an `Application`
    and exposes a fully functional HTTP `client` for making requests against
    the mounted ASGI app.

    After setup, the following attributes are available:
    - ``bed.client``: A :class:`~WebTestClient` backed by the real ASGI app.
    - ``bed.web_provider``: The :class:`~quadkit.web.di.provider.WebProvider` instance.
    - ``bed.container``: The DI container (for overrides and resolution).

    Args:
        provider_or_app: A :class:`~quadkit.web.di.provider.WebProvider` instance
            or a Quadkit :class:`~quadkit.app.base.Application`.
        name: Name of the test environment (defaults to "web-test-bed").
        raise_server_exceptions: Whether the test client re-raises server errors.
            Defaults to True. Set to False to inspect 5xx responses as assertions.
    """

    __test__ = False

    def __init__(
        self,
        provider_or_app: WebProvider | Application,
        name: str = "web-test-bed",
        raise_server_exceptions: bool = True,
    ) -> None:
        from quadkit.app.base import Application

        if isinstance(provider_or_app, Application):
            super().__init__(provider_or_app)
            # Find the WebProvider in the app
            from quadkit.web.di.provider import WebProvider

            self.web_provider = None
            for p in provider_or_app.providers:
                if isinstance(p, WebProvider):
                    self.web_provider = p
                    break
        else:
            super().__init__(name)
            self.web_provider = provider_or_app
            if hasattr(provider_or_app, "name"):
                self.use_provider(provider_or_app)
            else:
                # Raw ASGI callable: expose it as self.app and wire up client eagerly
                self.app = provider_or_app  # type: ignore[assignment]

        self._raise_server_exceptions = raise_server_exceptions
        # For raw ASGI apps, build the client immediately so tests work without async setup
        if self.app is not None and not hasattr(self, "_client_built"):
            self.client = WebTestClient(
                self.app,
                raise_server_exceptions=raise_server_exceptions,
            )

    async def setup(self) -> Any:
        """Boot the application and wire up the test client."""
        await super().setup()

        if not self.web_provider:
            from quadkit.contracts.web import WebProviderProtocol

            self.web_provider = await self.container.resolve_optional(  # type: ignore[union-attr]
                WebProviderProtocol
            )

        # After boot, the Starlette ASGI app is ready on the WebProvider or accessible via container
        self.client = WebTestClient(
            self.app if hasattr(self, "app") else self.web_provider,
            raise_server_exceptions=self._raise_server_exceptions,
        )
        return self.client

    async def __aenter__(self) -> Self:
        await self.setup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.teardown()

    def override(self, interface: type, implementation: Any) -> WebTestBed:
        """Override a DI registration for testing (fluent interface).

        Must be called before :meth:`setup`. Returns self for chaining.
        """
        super().override(interface, implementation)
        return self

    # Convenience HTTP methods delegates to client

    def get(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a GET request via the test client."""
        return self.client.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a POST request via the test client."""
        return self.client.post(url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a PUT request via the test client."""
        return self.client.put(url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a DELETE request via the test client."""
        return self.client.delete(url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> TestResponse:
        """Perform a PATCH request via the test client."""
        return self.client.patch(url, **kwargs)


def with_web(app: Application) -> WebTestBed:
    """Factory function to create a WebTestBed from an Application."""
    return WebTestBed(app)


__all__ = ["WebTestBed", "with_web"]
