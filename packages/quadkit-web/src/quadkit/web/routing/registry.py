"""Route registration and discovery.

This module provides the RouteRegistry.

Note: ControllerRegistry (in controller_registry.py) is the canonical source
for controller classes. RouteRegistry extends this to track route-level metadata.
Both registries work together: ControllerRegistry stores the controller classes
while RouteRegistry stores the resolved route paths and methods.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.primitives.registry import Registry
from quadkit.web.routing.controllers import Controller

if TYPE_CHECKING:
    from quadkit.web.routing.controller_registry import ControllerRegistry

logger = get_logger(__name__)


class RouteRegistry(Registry[str, dict[str, Any]]):
    """Registry for managing route registrations and discovery.

    Canonical source for routes: RouteRegistry.
    Use RouteRegistry for route-level operations (path, method, handler).
    Use ControllerRegistry for controller-level operations (class registration).
    """

    def __init__(self, debug: bool = False):
        super().__init__(name="routes")
        self._controllers: list[type[Controller]] = []
        self._debug = debug

    def register_controller(
        self,
        controller_cls: type[Controller],
        controller_registry: ControllerRegistry | None = None,
    ) -> None:
        """Register a controller class and synchronize to ControllerRegistry.

        Args:
            controller_cls: The controller class to register.
            controller_registry: If provided, also registers the class by name
                in the ControllerRegistry for atomic synchronization. This ensures
                a controller exists in both registries, preventing lookup inconsistencies.
        """
        if controller_cls not in self._controllers:
            self._controllers.append(controller_cls)

            # Register routes from controller
            routes = (
                controller_cls.collect_routes()
                if hasattr(controller_cls, "collect_routes")
                else []
            )
            for route_meta in routes:
                self._register_route(controller_cls, route_meta)

        # Synchronize to ControllerRegistry if provided
        # Only sync if not already registered to avoid RegistryAlreadyExistsError
        if controller_registry is not None:
            name = controller_cls.__name__
            if controller_registry.get(name) is None:
                controller_registry.register(name, controller_cls)

    def _register_route(
        self,
        controller_cls: type[Controller],
        route_meta: dict[str, Any],
    ) -> None:
        """Register a single route"""
        path = str(route_meta["path"])
        method = str(route_meta["method"]).upper()
        prefix = str(getattr(controller_cls, "prefix", "")).rstrip("/")

        # Prepend prefix
        if prefix:
            if not path.startswith("/"):
                path = f"/{path}"
            path = prefix if path == "/" else f"{prefix}{path}"

        # Ensure non-empty path
        if not path:
            path = "/"

        if path not in self._items:
            self._items[path] = {}

        if method in self._items[path]:
            # Duplicate registrations can occur during test collection or when
            # modules are imported multiple times. Treat as no-op to improve DX.
            logger.debug(
                "Route %s %s already registered, ignoring duplicate",
                method,
                path,
            )
            return

        # Capture best-effort origin metadata for diagnostics (only when debug mode is enabled)
        registered_file = None
        registered_line = None
        registered_stack = None
        if self._debug:
            try:
                stack = inspect.stack()
                if len(stack) > 1:
                    registered_file = stack[1].filename
                    registered_line = stack[1].lineno
                    registered_stack = [
                        f"{fi.function!s}@{fi.filename!s}:{fi.lineno!s}"
                        for fi in stack[1:6]
                    ]
            except (RuntimeError, OSError, AttributeError) as e:
                logger.debug(
                    "Failed to capture registration stack metadata for route %s %s: %s",
                    method,
                    path,
                    e,
                )

        self._items[path][method] = {
            "controller": controller_cls,
            "handler_name": route_meta["handler_name"],
            "response_model": route_meta.get("response_model"),
            "status_code": route_meta.get("status_code", 200),
            "summary": route_meta.get("summary"),
            "description": route_meta.get("description"),
            "tags": route_meta.get("tags", []),
            "registered_file": registered_file,
            "registered_line": registered_line,
            "registered_stack": registered_stack,
        }

    def get_all_routes(self) -> dict[str, dict[str, Any]]:
        """Get all registered routes"""
        return self._items.copy()

    def get_controllers(self) -> list[type[Controller]]:
        """Get all registered controllers"""
        return self._controllers.copy()

    def find_route(self, path: str, method: str) -> dict[str, Any] | None:
        """Find a route by path and method"""
        path_routes = self._items.get(path)
        if path_routes:
            return path_routes.get(str(method).upper())
        return None

    def get_routes_by_controller(
        self,
        controller_cls: type[Controller],
    ) -> list[dict[str, Any]]:
        """Get all routes for a specific controller"""
        routes = []
        for path, methods in self._items.items():
            for method, route_info in methods.items():
                if route_info["controller"] == controller_cls:
                    routes.append({"path": path, "method": method, **route_info})
        return routes

    def clear(self) -> None:
        """Clear all registrations"""
        super().clear()
        self._controllers.clear()


# Global registry instance — written to by @route decorators at import time.
# WebProvider registers this instance with the container so DI resolution
# and direct module access always return the same object.
route_registry = RouteRegistry()


def register_controller(controller_cls: type[Controller]) -> None:
    """Convenience function to register a controller.

    Registers the controller in both RouteRegistry and ControllerRegistry,
    ensuring synchronization and preventing lookup inconsistencies.
    """
    from quadkit.web.routing.controller_registry import controller_registry

    route_registry.register_controller(
        controller_cls,
        controller_registry=controller_registry,
    )


def get_route_registry() -> RouteRegistry:
    """Get the global route registry."""
    return route_registry
