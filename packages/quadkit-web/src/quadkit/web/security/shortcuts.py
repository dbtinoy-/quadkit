"""Shorthand guard decorators for common authorization patterns.

Provides concise aliases over :func:`~quadkit.web.security.guards.use_guards`
for the most frequent use cases.

Example::

    from quadkit.web import guard, roles

    @guard(AuthGuard)
    async def protected_route(self): ...

    @roles("admin", "moderator")
    async def admin_route(self): ...
"""

from __future__ import annotations

from typing import Any

from quadkit.web.security.guards import RoleGuard, use_guards


def guard(*guard_classes: type[Any] | Any) -> Any:
    """Concise alias for :func:`use_guards`.

    Attaches one or more guards to a route handler or controller class.
    Guards are executed in order; the first failure returns a 403 response.

    Args:
        *guard_classes: GuardProtocol classes or instances to apply.

    Returns:
        Decorator that attaches guards to the target.

    Example::

        @guard(AuthGuard)
        async def profile(self): ...

        @guard(AuthGuard, PermissionGuard("users:write"))
        async def create_user(self): ...
    """
    return use_guards(*guard_classes)


def roles(*role_names: str, authorizer: Any | None = None) -> Any:
    """Restrict a handler to users that have at least one of the given roles.

    The ``authorizer`` dependency must be injected.

    Args:
        *role_names: Required role names; user must hold at least one.
        authorizer: **Required** AuthorizerProtocol instance, typically resolved
            from the container during application startup.

    Returns:
        Decorator that attaches a :class:`RoleGuard` to the target.

    Example::

        authorizer = await container.resolve(AuthorizerProtocol)

        @roles("admin", authorizer=authorizer)
        async def admin_only(self): ...

        @roles("admin", "moderator", authorizer=authorizer)
        async def manage_content(self): ...
    """
    if authorizer is None:
        raise ValueError(
            "authorizer parameter is required. Inject it from the container at startup."
        )
    return use_guards(RoleGuard(*role_names, authorizer=authorizer))


__all__ = ["guard", "roles"]
