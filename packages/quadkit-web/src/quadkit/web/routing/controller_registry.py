"""Controller registration utilities for Quadkit Web Framework.

This module provides the ControllerRegistry.

Note: ControllerRegistry is the canonical source for controller classes.
RouteRegistry (in registry.py) extends this concept to track route metadata.
Both registries work together: ControllerRegistry stores the controller classes
while RouteRegistry stores the resolved route paths and methods.
"""

from __future__ import annotations

from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives.registry import Registry

logger = get_logger(__name__)


class ControllerRegistry(Registry[str, type]):
    """Registry for managing controller registrations.

    Canonical source for controllers: ControllerRegistry.
    Use ControllerRegistry for controller-level operations (class registration).
    Use RouteRegistry for route-level operations (path, method, handler).
    """

    def __init__(self) -> None:
        super().__init__(name="controllers")

    def register(
        self,
        key: str | type,
        value: type | None = None,
        *,
        allow_overwrite: bool | None = None,
    ) -> type | Any:
        """Register a controller class.

        Args:
            key: Component key or class
            value: The controller class to register
            allow_overwrite: Whether to allow overwriting an existing registration

        Returns:
            The registered controller class
        """
        controller_class: type | None
        if isinstance(key, type):
            controller_class = key
            name = getattr(controller_class, "__name__", str(controller_class))
        else:
            name = key
            controller_class = value

        if controller_class is None:
            # Decorator usage: @registry.register("name")
            def decorator(cls: type) -> type:
                super(ControllerRegistry, self).register(name, cls)
                return cls

            return decorator

        super().register(name, controller_class)
        return controller_class

    def get(self, name: str) -> type | None:  # type: ignore[override]
        """Get a controller class by name."""
        return super().get(name)

    def list_controllers(self) -> list[str]:
        """List all registered controller names."""
        return list(super().keys())

    def get_all_controllers(self) -> list[type]:
        """Get all registered controller classes."""
        return list(super().values())

    def clear(self) -> None:
        """Clear all registrations.

        Use in tests only to prevent test pollution between test cases.
        """
        super().clear()


def controller(name: str | None = None) -> Any:
    """Decorator to automatically register a controller class.

    Args:
        name: Optional controller name, defaults to class name

    Example:
        @controller()
        class UserController(Controller):
            @get("/users")
            async def get_users(self):
                return {"users": []}
    """

    def decorator(cls: type) -> type:
        # Register with controller registry
        controller_name = name or cls.__name__
        controller_registry.register(controller_name, cls)

        logger.debug(
            "Auto-registered controller %s from %s.%s",
            controller_name,
            cls.__module__,
            cls.__name__,
        )
        return cls

    return decorator


# Global controller registry instance
controller_registry = ControllerRegistry()
