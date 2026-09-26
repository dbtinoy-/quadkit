"""GuardProtocol services for authorization in Quadkit Framework"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from quadkit.auth.types import GuardContext
from quadkit.contracts.web import ResponseFactoryProtocol
from quadkit.contracts.web.guard import GuardProtocol
from quadkit.logging import get_logger
from quadkit.primitives.context import Context, get_request_context

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.web import ResponseProtocol

logger = get_logger(__name__)


def _get_request_resolver(request: Any) -> Any | None:
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(request)
    if resolver is not None:
        return resolver

    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        return scope.get("quadkit_resolver")

    return None


async def _get_request_context_user_id(request: Any) -> str | None:
    resolver = _get_request_resolver(request)
    if resolver is None:
        return None

    resolve_optional = getattr(resolver, "resolve_optional", None)
    if callable(resolve_optional):
        context = await resolve_optional(Context)
    else:
        context = await resolver.resolve(Context)
    if context is None:
        return None

    current = get_request_context(context.registry)
    return current.user_id if current is not None else None


class _GuardBase(ABC):
    """Private abstract base for auth guards; provides default handle_rejection."""

    @abstractmethod
    async def can_activate(self, context: GuardContext) -> bool:
        """Check if the guard allows the request to proceed"""

    async def handle_rejection(self, context: GuardContext) -> ResponseProtocol:
        """Handle guard rejection by returning appropriate response."""
        try:
            resolver = _get_request_resolver(context.request)
            if resolver is None:
                raise ValueError("No resolver found in context")
            response_factory = await resolver.resolve(ResponseFactoryProtocol)
        except ValueError as exc:
            raise RuntimeError(
                "ResponseFactoryProtocol not available — ensure the DI container is configured",
            ) from exc

        return cast(
            "ResponseProtocol",
            response_factory.json(
                {"error": "forbidden", "message": "Access denied"},
                status_code=403,
            ),
        )


class AuthGuard(_GuardBase):
    """GuardProtocol that requires authentication"""

    async def can_activate(self, context: GuardContext) -> bool:
        """Check if user is authenticated"""
        return context.user is not None or context.request_context_user_id is not None

    async def handle_rejection(self, context: GuardContext) -> ResponseProtocol:
        """Return 401 for unauthenticated requests."""
        try:
            resolver = _get_request_resolver(context.request)
            if resolver is None:
                raise ValueError("No resolver found in context")
            response_factory = await resolver.resolve(ResponseFactoryProtocol)
        except ValueError as exc:
            raise RuntimeError(
                "ResponseFactoryProtocol not available — ensure the DI container is configured",
            ) from exc

        return cast(
            "ResponseProtocol",
            response_factory.json(
                {"error": "unauthorized", "message": "Authentication required"},
                status_code=401,
            ),
        )


class RoleGuard(_GuardBase):
    """GuardProtocol that requires specific roles"""

    def __init__(self, *roles: str) -> None:
        self.required_roles = list(roles)

    async def can_activate(self, context: GuardContext) -> bool:
        """Check if user has required roles"""
        if not context.user:
            return False
        return any(context.user.has_role(role) for role in self.required_roles)


class PermissionGuard(_GuardBase):
    """GuardProtocol that requires specific permissions.

    By default **all** permissions must be granted.  ``require_all=False``
    opts into the previous any-of behavior explicitly.
    """

    def __init__(
        self,
        *permissions: str,
        require_all: bool = True,
    ) -> None:
        self.required_permissions = list(permissions)
        self.require_all = require_all

    async def can_activate(self, context: GuardContext) -> bool:
        """Check if user has required permissions"""
        if not context.user:
            return False

        # A PermissionGuard without declared permissions protects nothing;
        # fail closed.
        if not self.required_permissions:
            return False

        # Import here to avoid circular imports

        try:
            resolver = _get_request_resolver(context.request)

            from quadkit.contracts.auth import AuthProviderProtocol

            if resolver is None:
                return False

            auth_provider: Any = cast(
                "Any",
                await resolver.resolve(AuthProviderProtocol),
            )

            def _has(permission: str) -> bool:
                return bool(
                    auth_provider.has_any_permission(
                        cast("Any", context.user),
                        [permission],
                    )
                )

            if self.require_all:
                return all(_has(p) for p in self.required_permissions)
            return bool(
                auth_provider.has_any_permission(
                    cast("Any", context.user),
                    self.required_permissions,
                ),
            )
        except Exception:  # noqa: BLE001 — fail closed: any permission-check failure denies
            logger.warning("Failed to check permissions via container")
            return False


class CompositeGuard(_GuardBase):
    """GuardProtocol that combines multiple guards with AND logic"""

    def __init__(self, *guards: GuardProtocol) -> None:
        self.guards = guards

    async def can_activate(self, context: GuardContext) -> bool:
        """Check if all guards pass"""
        for guard in self.guards:
            if not await guard.can_activate(context):  # type: ignore[arg-type]
                return False
        return True


class AdminGuard(RoleGuard):
    """GuardProtocol that requires admin role"""

    def __init__(self) -> None:
        super().__init__("admin")


class UserGuard(AuthGuard):
    """GuardProtocol that requires any authenticated user"""


def use_guards(
    *guards: GuardProtocol,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Apply guards to a route handler (auth-scoped internal implementation).

    .. note::
        This is the auth-package-scoped version of ``use_guards``, intended for
        internal use within ``quadkit-auth``.  For general-purpose use outside
        the auth subsystem, prefer ``quadkit.security.guards.use_guards`` which
        integrates with ``GuardChain``.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract request from args (Starlette pattern)
            request = None
            for arg in args:
                if hasattr(arg, "state") and hasattr(arg, "headers"):
                    request = arg
                    break

            if not request and "request" in kwargs:
                request = kwargs["request"]

            if not request:
                # Fail closed: a guarded handler without a discoverable request
                # context must never run unguarded.
                raise ValueError(
                    "GuardProtocol requires request context. Ensure the handler "
                    "declares 'request' as a parameter."
                )

            # Always skip guards for OPTIONS requests (CORS preflight)
            if hasattr(request, "method") and request.method == "OPTIONS":
                return await func(*args, **kwargs)

            # Get user from request state
            user = getattr(request.state, "user", None)
            request_context_user_id = await _get_request_context_user_id(request)

            # Create guard context
            context = GuardContext(
                user=user,
                request=request,
                request_context_user_id=request_context_user_id,
            )

            # Check all guards
            for guard in guards:
                if not await guard.can_activate(context):  # type: ignore[arg-type]
                    return await guard.handle_rejection(context)  # type: ignore[arg-type]

            # All guards passed, proceed
            return await func(*args, **kwargs)

        # Store guards on function for introspection
        wrapper.__guards__ = guards  # type: ignore[attr-defined]
        return wrapper

    return decorator


class GuardFactory:
    """Factory for creating guards via dependency injection.

    This class handles the async resolution of guards from the DI container
    and provides synchronous access for use in decorators.
    """

    _instances: dict[str, GuardProtocol] = {}

    @classmethod
    async def get_guard(
        cls,
        guard_type: type[GuardProtocol],
        resolver: Any | None = None,
    ) -> GuardProtocol:
        """Get a guard instance, resolving from DI container if needed.

        Args:
            guard_type: The type of guard to get.
            resolver: Optional resolver to use.

        Returns:
            The guard instance.
        """
        from quadkit.di.resolution.context import get_resolver

        res = get_resolver(resolver)
        if res:
            guard = await res.resolve_optional(guard_type)
            if guard is not None:
                return guard
            logger.debug(
                "guard_resolution_failed",
                guard=guard_type.__name__,
                error="not registered",
            )

        key = guard_type.__name__
        if key not in cls._instances:
            cls._instances[key] = guard_type()
        return cls._instances[key]


def require_auth() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator requiring authentication.

    Uses GuardFactory to get the guard instance properly.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = None
            for arg in args:
                if hasattr(arg, "state") and hasattr(arg, "headers"):
                    request = arg
                    break

            if not request and "request" in kwargs:
                request = kwargs["request"]

            if not request:
                raise ValueError(
                    "GuardProtocol requires request context. Ensure the handler "
                    "declares 'request' as a parameter."
                )

            if hasattr(request, "method") and request.method == "OPTIONS":
                return await func(*args, **kwargs)

            user = getattr(request.state, "user", None)
            # BUG #39: GuardContext is a DomainModel whose __init__ only
            # binds keyword arguments (positional args are silently
            # dropped), so the old positional call produced user=None and
            # @require_auth rejected even authenticated users.
            context = GuardContext(request=request, user=user)

            guard = await GuardFactory.get_guard(AuthGuard, request)  # type: ignore[arg-type]
            if not await guard.can_activate(context):  # type: ignore[arg-type]
                return await guard.handle_rejection(context)  # type: ignore[arg-type]

            return await func(*args, **kwargs)

        wrapper.__guard_type__ = AuthGuard  # type: ignore[attr-defined]
        return wrapper

    return decorator


def require_admin() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator requiring admin role.

    Uses GuardFactory to get the guard instance properly.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = None
            for arg in args:
                if hasattr(arg, "state") and hasattr(arg, "headers"):
                    request = arg
                    break

            if not request and "request" in kwargs:
                request = kwargs["request"]

            if not request:
                raise ValueError(
                    "GuardProtocol requires request context. Ensure the handler "
                    "declares 'request' as a parameter."
                )

            if hasattr(request, "method") and request.method == "OPTIONS":
                return await func(*args, **kwargs)

            user = getattr(request.state, "user", None)
            context = GuardContext(request=request, user=user)

            guard = await GuardFactory.get_guard(AdminGuard, request)  # type: ignore[arg-type]
            if not await guard.can_activate(context):  # type: ignore[arg-type]
                return await guard.handle_rejection(context)  # type: ignore[arg-type]

            return await func(*args, **kwargs)

        wrapper.__guard_type__ = AdminGuard  # type: ignore[attr-defined]
        return wrapper

    return decorator


def require_role(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator requiring specific roles"""
    return use_guards(RoleGuard(*roles))  # type: ignore[arg-type]


def require_permission(
    *permissions: str,
    require_all: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator requiring specific permissions.

    ``require_all=True`` (default) requires every permission; pass
    ``require_all=False`` to require any one of them.
    """
    return use_guards(
        PermissionGuard(*permissions, require_all=require_all),  # type: ignore[arg-type]
    )


__all__ = [
    "AdminGuard",
    "AuthGuard",
    "CompositeGuard",
    "GuardContext",
    # GuardProtocol classes
    "GuardProtocol",
    "PermissionGuard",
    "RoleGuard",
    "UserGuard",
    "require_admin",
    "require_auth",
    "require_permission",
    "require_role",
    # Decorators (snake_case only)
    "use_guards",
]
