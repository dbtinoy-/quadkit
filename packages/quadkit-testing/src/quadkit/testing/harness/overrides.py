from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, TypeVar

# Use TYPE_CHECKING to avoid circular imports if necessary,
# although Container is usually safe to import in testing.

if TYPE_CHECKING:
    from collections.abc import Iterator

    from quadkit.di.container import Container

T = TypeVar("T")


@contextlib.contextmanager
def override(
    container: Container, interface: type[T], implementation: Any
) -> Iterator[None]:
    """Context manager to temporarily override a dependency in the container.

    Example:
        with override(container, UserService, MockUserService()):
            # UserService resolves to MockUserService here
            ...
    """
    # Use internal API to access registry for temporary override
    registry = container._Container__service_resolver._registry  # type: ignore[attr-defined]
    store = registry.store

    # Store the original descriptor if it exists
    original_descriptor = store.get(interface)

    # Create an override descriptor for the replacement instance
    from quadkit.di.resolution.descriptor import ServiceDescriptor, ServiceScope

    override_descriptor = ServiceDescriptor(
        service_type=interface,
        implementation=type(implementation),
        scope=ServiceScope.SINGLETON,
        instance=implementation,
        is_instantiated=True,
    )
    store.add(override_descriptor)

    try:
        yield
    finally:
        # Restore original state
        if original_descriptor is not None:
            store.add(original_descriptor)
        else:
            store._descriptors.pop(interface, None)
