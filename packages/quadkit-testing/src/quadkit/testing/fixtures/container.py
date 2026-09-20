"""ContainerTestFixture — isolated DI container for test setup/teardown.

Provides a scoped, auto-disposed DI container that each test receives
fresh, with registered mock implementations for all common protocols.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self, TypeVar

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.testing.harness.container import QuadkitContainerHarness

T = TypeVar("T")

logger = get_logger(__name__)


class ContainerTestFixture:
    """Isolated DI container scoped to a single test.

    Wraps :class:`~quadkit.testing.harness.container.QuadkitContainerHarness` with automatic
    disposal and convenience helpers for registering overrides.

    Intended to be used through the :func:`test_container` pytest fixture so
    each test receives a fully isolated container with fresh mock registrations.

    Typical usage (via pytest fixture)::

        async def test_my_service(test_container: ContainerTestFixture) -> None:
            test_container.mock(UserRepository, FakeUserRepository())
            service = await test_container.get(UserService)
            result = await service.create(email="a@b.com")
            assert result.is_ok()

    Direct usage (as async context manager)::

        async with ContainerTestFixture() as fixture:
            fixture.mock(CacheBackendProtocol, FakeCache())
            svc = await fixture.get(MyService)
    """

    def __init__(self, *, register_mocks: bool = False) -> None:
        # Local import breaks the fixtures → container → fixtures circular dependency.
        from quadkit.testing.harness.container import QuadkitContainerHarness

        self._container: QuadkitContainerHarness = QuadkitContainerHarness(
            register_mocks=register_mocks
        )
        self._disposed: bool = False

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def get(self, interface: type[T]) -> T:
        """Resolve *interface* from the container.

        Args:
            interface: The protocol or class to resolve.

        Returns:
            The resolved instance.

        Raises:
            RuntimeError: If the fixture has already been disposed.
        """
        if self._disposed:
            msg = "ContainerTestFixture has already been disposed"
            raise RuntimeError(msg)
        return await self._container.resolve(interface)

    async def get_optional(self, interface: type[T]) -> T | None:
        """Resolve *interface*, returning ``None`` if not registered.

        Args:
            interface: The protocol or class to resolve.

        Returns:
            The resolved instance, or ``None`` if not found.
        """
        if self._disposed:
            return None
        return await self._container.resolve_optional(interface)

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def mock(self, interface: type[T], mock_obj: Any) -> None:
        """Register *mock_obj* as the singleton for *interface*.

        This is the primary way to wire test doubles into the container.

        Args:
            interface: The protocol or class to override.
            mock_obj: The mock/fake/stub to register.
        """
        self._container.mock(interface, mock_obj)

    @asynccontextmanager
    async def override(
        self,
        interface: type[T],
        mock_obj: Any,
    ) -> AsyncGenerator[None, None]:
        """Register *mock_obj* for *interface* for the duration of the block.

        Because each test receives a fresh container, this is equivalent to
        calling :meth:`mock` for the lifetime of the scope. It exists purely
        for readability in tests that want to be explicit about scope.

        Args:
            interface: The protocol or class to override.
            mock_obj: The mock/fake/stub to register.

        Yields:
            Nothing; the override is active for the body of the block.
        """
        self._container.mock(interface, mock_obj)
        yield

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def dispose(self) -> None:
        """Dispose the container and release all resources.

        Idempotent — safe to call multiple times.
        """
        if not self._disposed:
            self._disposed = True
            try:
                await self._container.dispose()
            except Exception as e:  # noqa: BLE001
                logger.debug(
                    "container_dispose_error", error=str(e)
                )  # Best-effort teardown — never fail a test on cleanup

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        """Enter the async context manager, returning self."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """Exit the async context manager, disposing the container."""
        await self.dispose()

    # ------------------------------------------------------------------
    # Raw container access
    # ------------------------------------------------------------------

    @property
    def container(self) -> QuadkitContainerHarness:
        """Return the underlying :class:`QuadkitContainerHarness`.

        Use this for advanced scenarios that require direct container access.
        Prefer :meth:`get` and :meth:`mock` for normal test usage.
        """
        return self._container


__all__ = ["ContainerTestFixture"]
