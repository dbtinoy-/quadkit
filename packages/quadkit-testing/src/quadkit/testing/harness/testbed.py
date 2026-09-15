"""AppTestBed — one-line test harness for Quadkit applications.

Boots an Application (or factory) with optional DI service overrides and
provides an HTTP test client. Intended for integration tests::

    async with AppTestBed.from_factory(
        "my_app.app:create_app",
        overrides={UserRepository: MockUserRepository()},
    ) as bed:
        response = await bed.client.get("/api/v1/users/1")
        assert response.status_code == 200
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class AppTestBed:
    """Test harness that boots the application with optional DI overrides.

    Attributes:
        app: The booted :class:`~quadkit.app.base.Application`.
        container: The DI container for direct service resolution.
        client: HTTP test client backed by the real ASGI app.
    """

    __test__ = False

    def __init__(self) -> None:
        self.app: Any = None
        self.container: Any = None
        self.client: Any = None
        self._web_provider: Any = None

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    @asynccontextmanager
    async def from_factory(
        cls,
        factory: str | Any,
        overrides: dict[type, Any] | None = None,
    ) -> AsyncIterator[AppTestBed]:
        """Create a test bed from an application factory.

        Args:
            factory: Either a dotted import string (``"my_app.app:create_app"``)
                or a callable that returns an
                :class:`~quadkit.app.base.Application`.
            overrides: Optional dict mapping service types to replacement
                instances.  Applied after providers register but before boot.

        Yields:
            A fully booted :class:`AppTestBed`.

        Example::

            async with AppTestBed.from_factory(
                "my_app.app:create_app",
                overrides={EmailService: MockEmailService()},
            ) as bed:
                resp = await bed.client.get("/health")
                assert resp.status_code == 200
        """
        bed = cls()
        app = bed._resolve_factory(factory)()

        # Apply overrides via a late-running provider (priority 999) so that
        # the overrides take effect AFTER all regular providers register.
        if overrides:
            from quadkit.di.provider import Provider

            _overrides = dict(overrides)

            class _OverrideProvider(Provider):
                def __init__(self) -> None:
                    super().__init__(name="_testbed_overrides")
                    self.priority = 999  # type: ignore[assignment]

                async def register(self, container: Any) -> None:
                    for svc_type, instance in _overrides.items():
                        container.singleton(svc_type, instance)

            app.add_provider(_OverrideProvider())

        await app.start()
        bed.app = app
        bed.container = app.container

        # Locate WebProvider to get the ASGI app
        try:
            from quadkit.web.di.provider import WebProvider

            for provider in app.providers:
                if isinstance(provider, WebProvider):
                    bed._web_provider = provider
                    break
        except ImportError:
            pass

        asgi_app = (
            bed._web_provider.starlette
            if bed._web_provider and bed._web_provider.starlette
            else None
        )
        if asgi_app is not None:
            bed.client = _build_test_client(asgi_app)

        try:
            yield bed
        finally:
            await app.stop()

    @classmethod
    @asynccontextmanager
    async def from_app(
        cls,
        app: Any,
        overrides: dict[type, Any] | None = None,
    ) -> AsyncIterator[AppTestBed]:
        """Create a test bed from an already-constructed Application.

        Args:
            app: An :class:`~quadkit.app.base.Application` instance.
            overrides: Optional DI overrides (same as :meth:`from_factory`).

        Yields:
            A fully booted :class:`AppTestBed`.
        """
        async with cls.from_factory(lambda: app, overrides=overrides) as bed:
            yield bed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_factory(factory: str | Any) -> Any:
        """Resolve a factory from a dotted string or return callable as-is."""
        if callable(factory):
            return factory
        if isinstance(factory, str):
            if ":" in factory:
                module_path, attr = factory.rsplit(":", 1)
            else:
                module_path, attr = factory.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, attr)
        raise TypeError(
            f"factory must be a callable or dotted string, got {type(factory)}"
        )


def _build_test_client(asgi_app: Any) -> Any:
    """Create an httpx-based async test client for an ASGI app."""
    try:
        import httpx

        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url="http://testserver",
        )
    except ImportError:
        # Fallback to starlette TestClient (sync)
        try:
            from starlette.testclient import TestClient

            return TestClient(asgi_app)
        except ImportError:
            return None


__all__ = ["AppTestBed"]
