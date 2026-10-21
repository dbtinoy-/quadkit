"""
GuardProtocol system for request authorization.

Guards are executed before route handlers to validate authorization.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
import inspect
from typing import Any, TypeVar, cast

from starlette.requests import Request

from quadkit.contracts import AuthorizerProtocol
from quadkit.contracts.web.guard import GuardProtocol
from quadkit.result import Err, Ok, Result
from quadkit.web.protocols import (
    ExecutionContextProtocol as _BaseExecutionContext,
)
from quadkit.web.transport.responses import JSONResponse

_Decorated = TypeVar("_Decorated")


@dataclass(frozen=True)
class GuardRejection:
    """Represents a guard denial with error details."""

    error: str = "Unauthorized"
    message: str = "Access denied"
    status_code: int = 403


def _extract_request(context: Any) -> Any:
    """Return the raw request from either an ExecutionContextProtocol or a plain request."""
    if isinstance(context, _BaseExecutionContext):
        return context.request
    return context


class AuthGuard(ABC):
    """
    GuardProtocol that checks if user is authenticated.

    Looks for user in request.state.user (set by auth middleware).
    """

    async def can_activate(self, context: Any) -> bool:
        """Check if user is authenticated."""
        request = _extract_request(context)
        user = getattr(request.state, "user", None)
        return user is not None


class RoleGuard(ABC):
    """
    GuardProtocol that checks if user has required role(s).

    The authorizer must be injected at guard instantiation time (constructor injection).

    Usage:
        authorizer = await container.resolve(AuthorizerProtocol)
        @use_guards(RoleGuard(*required_roles, authorizer=authorizer))
        async def admin_only(self):
            ...
    """

    def __init__(self, *required_roles: str, authorizer: AuthorizerProtocol) -> None:
        self.required_roles = set(required_roles)
        self._authorizer = authorizer

    async def can_activate(self, context: Any) -> bool:
        """Check if user has required role using AuthorizerProtocol."""
        request = _extract_request(context)
        user = getattr(request.state, "user", None)
        if not user:
            return False

        # Check access with authorizer (handles superuser bypass and inheritance)
        return await self._authorizer.check_access(user, self.required_roles)


class PermissionGuard(ABC):
    """
    GuardProtocol that checks if user has required permission(s).

    The authorizer must be injected at guard instantiation time (constructor injection).

    By default **all** requested permissions must be granted (``require_all=True``).
    ``require_all=False`` is supported for explicit "any of" routes; using the
    opt-in form makes the security boundary obvious at the point of use.

    Usage:
        authorizer = await container.resolve(AuthorizerProtocol)
        @use_guards(PermissionGuard("users:write", "users:read", authorizer=authorizer))
        async def create_user(self):
            ...
    """

    def __init__(
        self,
        *required_permissions: str,
        authorizer: AuthorizerProtocol,
        require_all: bool = True,
    ) -> None:
        self.required_permissions = set(required_permissions)
        self._authorizer = authorizer
        self.require_all = require_all

    async def can_activate(self, context: Any) -> bool:
        """Check if user has required permissions using AuthorizerProtocol."""
        request = _extract_request(context)
        user = getattr(request.state, "user", None)
        if not user:
            return False

        # A PermissionGuard without any declared permissions is meaningless;
        # fail closed rather than accidentally protecting nothing.
        if not self.required_permissions:
            return False

        # Check each permission against the authorizer.  A permission string is
        # treated as "resource.action" when it contains a dot, otherwise as a
        # bare action on the resource named by the whole string.
        async def _matches(perm: str) -> bool:
            parts = perm.split(".", 1)
            resource = parts[0]
            action = parts[1] if len(parts) > 1 else perm
            can = getattr(self._authorizer, "can", None)
            if not callable(can):
                return False
            return bool(await can(user, action, resource))

        if self.require_all:
            for perm in self.required_permissions:
                if not await _matches(perm):
                    return False
            return True

        for perm in self.required_permissions:
            if await _matches(perm):
                return True
        return False


def use_guards(*guards: type[Any] | Any) -> Callable[[_Decorated], _Decorated]:
    """
    Decorator to attach guards to a route handler or controller.

    Guards are executed in order before the route handler.
    If any guard returns False, the request is rejected.

    **Guards requiring dependencies (like RoleGuard, PermissionGuard) must
    be instantiated with those dependencies passed to the constructor.**

    Usage:
        @use_guards(AuthGuard)
        async def protected_route(self):
            ...

        # With injected dependencies
        authorizer = await container.resolve(AuthorizerProtocol)
        @use_guards(AuthGuard, RoleGuard("admin", authorizer=authorizer))
        async def admin_route(self):
            ...
    """

    def decorator(target: _Decorated) -> _Decorated:
        # Store guards metadata
        guard_instances = []
        for guard in guards:
            if isinstance(guard, type):
                guard_instances.append(guard())
            else:
                guard_instances.append(guard)

        cast("Any", target).__guards__ = guard_instances

        # Wrap the function to execute guards
        if inspect.iscoroutinefunction(target):
            target_callable = cast("Callable[..., Any]", target)

            @wraps(target_callable)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Find request in kwargs first, then scan positional args
                request = kwargs.get("request")
                if request is None:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break
                if request is None:
                    qualname = getattr(
                        target_callable, "__qualname__", repr(target_callable)
                    )
                    raise RuntimeError(
                        "GuardProtocol requires request context for "
                        f"{qualname!r}. Ensure the handler declares "
                        "'request: Request' as a parameter.",
                    )

                result = await execute_guards(guard_instances, request)
                if result.is_err():
                    rejection = result.unwrap_err()
                    return JSONResponse(
                        {"error": rejection.error, "message": rejection.message},
                        status_code=rejection.status_code,
                    )

                return await target_callable(*args, **kwargs)

            return cast("_Decorated", wrapper)
        return target

    return decorator


async def execute_guards(
    guards: list[Any],
    request: Request,
) -> Result[None, GuardRejection]:
    """
    Execute a list of guards.

    Args:
        guards: List of guard instances
        request: The incoming request

    Returns:
        Ok(None) if all guards pass, Err(GuardRejection) if any guard fails
    """
    for guard in guards:
        can_proceed = await guard.can_activate(request)
        if not can_proceed:
            return Err(GuardRejection())

    return Ok(None)


def require_admin(target: Any = None, *, authorizer: Any = None) -> Any:
    """
    Convenience decorator for admin-only routes.

    The ``authorizer`` dependency must be injected.

    Can be used either as:
        @require_admin(authorizer=auth)
        async def handler(...):
            ...

    or as:
        @require_admin
        async def handler(...):
            ...

    Args:
        target: When used without parentheses, the decorated function.
        authorizer: **Required** AuthorizerProtocol instance.
    """
    if authorizer is None:
        raise ValueError(
            "authorizer parameter is required. Inject it from the container at startup."
        )

    decorator = use_guards(RoleGuard("admin", authorizer=authorizer))
    # If used without parentheses
    if target is not None:
        return decorator(target)
    return decorator


__all__ = [
    "AuthGuard",
    "GuardProtocol",
    "GuardRejection",
    "PermissionGuard",
    "RoleGuard",
    "execute_guards",
    "require_admin",
    "use_guards",
]
