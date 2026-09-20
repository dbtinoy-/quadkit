"""Route groups for organizing controllers with shared configuration.

Provides RouteGroup for grouping controllers with shared prefix, guards, and interceptors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.web.routing.controllers import Controller


class RouteGroup:
    """Groups controllers with shared configuration.

    Usage:
        admin_group = RouteGroup(
            prefix="/api/v1/admin",
            controllers=[UserController, RoleController],
            guards=[AuthGuard, RoleGuard("admin")],
            interceptors=[AuditLogInterceptor],
        )

        # Register with WebProvider
        provider = WebProvider(
            route_groups=[admin_group],
        )
    """

    def __init__(
        self,
        prefix: str,
        controllers: list[type[Controller]],
        guards: list[Any] | None = None,
        interceptors: list[Any] | None = None,
        middleware: list[Any] | None = None,
    ):
        self.prefix = prefix
        self.controllers = controllers
        self.guards = guards or []
        self.interceptors = interceptors or []
        self.middleware = middleware or []

    def apply_guards(self, controller_cls: type[Controller]) -> type[Controller]:
        """Apply group's guards to controller by creating a subclass."""
        existing_guards = getattr(controller_cls, "_guards", [])
        return type(
            f"{controller_cls.__name__}_with_guards",
            (controller_cls,),
            {"_guards": existing_guards + self.guards},
        )

    def apply_interceptors(self, controller_cls: type[Controller]) -> type[Controller]:
        """Apply group's interceptors to controller by creating a subclass."""
        existing_interceptors = getattr(controller_cls, "_interceptors", [])
        return type(
            f"{controller_cls.__name__}_with_interceptors",
            (controller_cls,),
            {"_interceptors": existing_interceptors + self.interceptors},
        )

    def finalize(self) -> list[type[Controller]]:
        """Apply group configuration to all controllers by creating subclasses."""
        results = []
        for controller in self.controllers:
            controller = self.apply_guards(controller)
            controller = self.apply_interceptors(controller)

            # Get existing prefix and combine
            existing_prefix = getattr(controller, "prefix", "")
            if existing_prefix:
                # Combine prefixes
                combined_prefix = self.prefix.rstrip("/") + existing_prefix
            else:
                combined_prefix = self.prefix

            # Create final subclass with prefix
            results.append(
                type(
                    f"{controller.__name__}_finalized",
                    (controller,),
                    {"prefix": combined_prefix},
                ),
            )

        return results


def group(
    prefix: str,
    guards: list[Any] | None = None,
    interceptors: list[Any] | None = None,
    middleware: list[Any] | None = None,
) -> Callable[[list[type[Controller]]], RouteGroup]:
    """Create a route group.

    Usage:
        @group("/api/v1/admin", guards=[AuthGuard])
        class AdminController(Controller):
            ...
    """

    def decorator(controllers: list[type[Controller]]) -> RouteGroup:
        return RouteGroup(
            prefix=prefix,
            controllers=controllers,
            guards=guards,
            interceptors=interceptors,
            middleware=middleware,
        )

    return decorator
