"""TestContainer implementation for Quadkit testing."""

from __future__ import annotations

import typing
from typing import Any, TypeVar

from quadkit.di.container import Container
from quadkit.result import Err, Ok, Result
from quadkit.testing.fixtures.containers import ContainerFactory

T = TypeVar("T")


# Renamed to avoid pytest collection warning since classes starting with "Test"
# with __init__ are treated as test classes
class QuadkitContainerHarness(Container):
    """Standardized DI container for isolated component testing.

    This container automatically registers common mock providers and
    mock component implementations (LockStore, PubSubProtocol, etc.) to
    provide an stable baseline for unit and integration tests.

    Usage::

        container = QuadkitContainerHarness()
        # Common mocks are already registered

        # Add your concrete provider for testing
        container.register(MyProvider())

        # Override specific mocks if needed
        container.singleton(DatabaseProviderProtocol, MockDB())

        service = await container.resolve(MyService)
    """

    __test__ = False  # Prevent pytest from collecting this class

    def __init__(self, register_mocks: bool = True) -> None:
        super().__init__(testing_mode=True)
        if register_mocks:
            factory = ContainerFactory()
            factory._register_common_protocols(self)

    def override(self, interface: type[T], implementation: Any) -> Any:
        """Context manager to temporarily override a dependency.

        Example:
            with container.override(UserService, MockUserService()):
                ...
        """
        from quadkit.testing.harness.overrides import override as _override

        return _override(self, interface, implementation)

    def mock(self, interface: type[T], mock_obj: Any) -> None:
        """Register a mock implementation directly as a singleton."""
        self.singleton(interface, mock_obj)

    async def try_resolve(self, interface: type[T]) -> Result[T, Exception]:
        """Resolve *interface* from the container, wrapping the outcome in ``Result``.

        This is the ``Result``-returning counterpart to :meth:`resolve`.  Use
        it when you need to assert that a dependency *fails* to resolve — for
        example to verify that a required binding is absent or mis-configured.

        Returns:
            ``Ok(instance)`` on success, ``Err(exception)`` if resolution
            raises for any reason (missing binding, circular dependency, etc.).

        Example::

            result = await container.try_resolve(MyService)
            assert result.is_err()
            assert isinstance(result.unwrap_err(), ResolutionError)
        """
        try:
            instance = await self.resolve(interface)
            return Ok(instance)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    def bind(self, protocol: type[T], implementation: Any) -> None:
        """Register *implementation* as *protocol* with runtime protocol validation.

        If *protocol* is decorated with ``@runtime_checkable``, this method
        verifies that *implementation* is an instance of *protocol* before
        registering it.  Non-runtime-checkable protocols are accepted as-is
        (mypy / pyright catch mismatches at type-check time).

        Args:
            protocol: The contract / protocol type to register.
            implementation: The concrete object implementing *protocol*.

        Raises:
            TypeError: When *protocol* is ``@runtime_checkable`` and
                *implementation* does not satisfy ``isinstance`` check.

        Example::

            container.bind(CacheBackendProtocol, FakeCache())
        """
        is_runtime_checkable = (
            isinstance(protocol, type)
            and issubclass(protocol, typing.Protocol)  # type: ignore[arg-type]
            and getattr(protocol, "_is_runtime_protocol", False)
        )
        if is_runtime_checkable and not isinstance(implementation, protocol):
            raise TypeError(
                f"{implementation!r} does not implement protocol {protocol.__name__!r}. "
                f"Ensure the class defines all required methods/attributes."
            )
        self.singleton(protocol, implementation)


__all__ = ["QuadkitContainerHarness"]
