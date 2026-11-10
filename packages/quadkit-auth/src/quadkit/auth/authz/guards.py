"""Authorization guards and route protection decorators.

Provides :class:`AuthorizationGuard` and :class:`RouteGuard` for RBAC/ABAC
checks, and decorator helpers (:func:`require_auth`, :func:`require_roles`,
:func:`require_permissions`, :func:`optional_auth`) that protect route
handlers.

All guards delegate actual permission evaluation to
:class:`~quadkit.auth.authz.service.AuthorizationService`, which is either
injected at construction time or created as a default instance.

Example::

    from quadkit.auth.authz.guards import require_auth, require_roles

    @require_auth(roles=["admin"])
    async def admin_endpoint(request):
        ...

    @require_roles("editor", "admin")
    async def editor_endpoint(request):
        ...
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse

from quadkit.auth.authz.service import AuthorizationService
from quadkit.contracts.web.security_metadata import (
    HTTP_BEARER_DOCUMENTATION_ATTRIBUTE,
    HttpBearerDocumentation,
    HttpErrorMessageDocumentation,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.auth.models.user import User

logger = get_logger(__name__)


def _find_request(args: tuple, kwargs: dict) -> Any:
    """Extract the first Starlette-like request from positional or keyword args."""
    for arg in args:
        if hasattr(arg, "state") and hasattr(arg, "headers"):
            return arg
    return kwargs.get("request")


async def _holds_permission(
    service: AuthorizationService, user: User, perm: str
) -> bool:
    """Return ``True`` when *user* holds the permission string *perm*.

    Permission strings are ``resource.action`` (the shape
    :meth:`AuthorizationService.can` composes from its arguments), so a
    dotted requirement is split at the last dot and evaluated through
    ``can`` — which walks role inheritance, ABAC policies, and
    delegations. A dot-less string is a bare scope (``"write"``,
    ``"admin"``) matched directly against the user's permission
    patterns.

    Passing the whole string as both arguments (the previous shape)
    composed ``perm.perm`` as the required grant, so an exact
    ``orders.read`` grant never satisfied a ``orders.read``
    requirement; only wildcard grants slipped through by prefix.
    """
    resource, dot, action = perm.rpartition(".")
    if not dot:
        return service.has_any_permission(user, [perm])
    return await service.can(user, action, resource)


async def _resolve_authorization_service(request: Any) -> AuthorizationService | None:
    """The app's DI-registered :class:`AuthorizationService`, if reachable.

    The decorators run outside the container, so without this lookup
    every check evaluates against a fresh service whose role registry
    is empty — role-derived permissions (and role inheritance) would
    never resolve even when the app configured them in ``auth.roles``.
    Resolution goes through the request's DI resolver, the same channel
    ``quadkit.auth.web.guards`` uses; any failure falls back to ``None``
    and the caller keeps today's default-service behavior.
    """
    try:
        from quadkit.di.resolution.context import get_resolver

        resolver = get_resolver(request)
        if resolver is None:
            return None
        service = await resolver.resolve(AuthorizationService)
    except Exception:  # noqa: BLE001 — resolution failure must not 500 the route
        return None
    return service if isinstance(service, AuthorizationService) else None


class AuthorizationGuard:
    """GuardProtocol that checks user roles and/or permissions.

    Args:
        roles: Required role names (any match is sufficient).
        permissions: Required permission strings (all must match).
        auth_service: Optional pre-built :class:`AuthorizationService` instance.
            When ``None``, a default instance is created on first use.
    """

    def __init__(
        self,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        auth_service: AuthorizationService | None = None,
    ) -> None:
        self.roles: list[str] = list(roles or [])
        self.permissions: list[str] = list(permissions or [])
        self._auth_service: AuthorizationService | None = auth_service

    async def check_authorization(self, user: User | None) -> bool:
        """Return ``True`` if *user* satisfies all role and permission requirements.

        Args:
            user: The authenticated user, or ``None`` for anonymous requests.

        Returns:
            ``False`` if user is ``None`` or inactive; delegates to
            :class:`~quadkit.auth.authz.service.AuthorizationService` for
            actual role/permission checks.
        """
        if user is None:
            return False
        if isinstance(user, dict):
            if not user.get("is_active", True):
                return False
        elif hasattr(user, "is_active") and not user.is_active:
            return False

        service = (
            self._auth_service
            if self._auth_service is not None
            else AuthorizationService()
        )

        if self.roles:
            if not service.has_any_role(user, list(self.roles)):
                return False

        if self.permissions:
            for perm in self.permissions:
                if not await _holds_permission(service, user, perm):
                    return False

        return True

    def get_error_message(self) -> str:
        """Build a human-readable description of the requirements.

        Returns:
            A string listing the required roles and/or permissions.
        """
        parts: list[str] = []
        if self.roles:
            parts.append(f"Required roles: {', '.join(sorted(self.roles))}")
        if self.permissions:
            parts.append(f"Required permissions: {', '.join(sorted(self.permissions))}")
        return "; ".join(parts) if parts else "Authorization required"


class RouteGuard:
    """Wraps an :class:`AuthorizationGuard` and provides HTTP response helpers.

    Args:
        guard: The underlying :class:`AuthorizationGuard` to delegate to.
    """

    def __init__(self, guard: AuthorizationGuard) -> None:
        self._guard = guard

    async def check_access(self, user: User | None) -> bool:
        """Delegate to the underlying guard's ``check_authorization``.

        Args:
            user: The authenticated user, or ``None``.
        """
        return await self._guard.check_authorization(user)

    async def get_deny_response(self) -> JSONResponse:
        """Build a 403 JSON response describing what was required.

        Returns:
            A :class:`starlette.responses.JSONResponse` with status 403.
        """
        return JSONResponse(
            {"error": "forbidden", "message": self._guard.get_error_message()},
            status_code=403,
        )


def authorization_documentation(
    *,
    roles: list[str] | tuple[str, ...] | None = None,
    permissions: list[str] | tuple[str, ...] | None = None,
    optional: bool = False,
) -> HttpBearerDocumentation | None:
    """Describe this native decorator without executing a guard or policy.

    Only the direct authorization branch owns the 403 envelope. Outer
    middleware can answer 401 first; optional and DI-replaced guards differ.
    """
    if optional:
        return None
    rejections = (
        (
            HttpErrorMessageDocumentation(
                403, "forbidden", "Authorization requirements not met."
            ),
        )
        if roles or permissions
        else ()
    )
    return HttpBearerDocumentation(rejections=rejections)


def require_auth(
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    optional: bool = False,
) -> Callable[[Callable], Callable]:
    """Decorator that protects a route handler with authentication and RBAC/ABAC checks.

    Args:
        roles: Required role names.  Any single matching role is sufficient.
        permissions: Required permission strings.  All must be satisfied.
        optional: When ``True``, allow unauthenticated requests to proceed
            (user will simply be ``None`` in ``request.state``).

    Returns:
        A decorator that wraps the route handler.

    Raises:
        ValueError: If no request object can be found in the handler's arguments.
    """
    guard = AuthorizationGuard(roles=roles, permissions=permissions)
    # The app's AuthorizationService, resolved lazily from the first
    # request's DI resolver and memoized (it is registered as a
    # singleton). Only successes are memoized: an early request that
    # beats container boot must not pin the empty-registry fallback.
    resolved_service: list[AuthorizationService] = []

    async def _guard_for(request: Any) -> AuthorizationGuard:
        if not resolved_service:
            service = await _resolve_authorization_service(request)
            if service is not None:
                resolved_service.append(service)
        if not resolved_service:
            return guard
        return AuthorizationGuard(
            roles=guard.roles,
            permissions=guard.permissions,
            auth_service=resolved_service[0],
        )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _find_request(args, kwargs)

            if request is None:
                if optional:
                    return await func(*args, **kwargs)
                raise ValueError("Could not find request object in handler arguments")

            user = getattr(request.state, "user", None)

            if user is None:
                if optional:
                    return await func(*args, **kwargs)
                return JSONResponse(
                    {"error": "unauthorized", "message": "Authentication required"},
                    status_code=401,
                )

            # No role/permission requirements → auth alone is sufficient
            if not roles and not permissions:
                return await func(*args, **kwargs)

            effective_guard = await _guard_for(request)
            if not await effective_guard.check_authorization(user):
                return JSONResponse(
                    {
                        "error": "forbidden",
                        "message": effective_guard.get_error_message(),
                    },
                    status_code=403,
                )

            return await func(*args, **kwargs)

        documentation = authorization_documentation(
            roles=roles, permissions=permissions, optional=optional
        )
        if documentation is not None:
            setattr(wrapper, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE, documentation)
        return wrapper

    return decorator


def require_roles(*roles: str) -> Callable[[Callable], Callable]:
    """Shorthand decorator requiring the user to have at least one of *roles*.

    Args:
        *roles: Role names that are acceptable.

    Returns:
        A decorator equivalent to ``require_auth(roles=list(roles))``.
    """
    return require_auth(roles=list(roles))


def require_permissions(*permissions: str) -> Callable[[Callable], Callable]:
    """Shorthand decorator requiring the user to hold all of *permissions*.

    Args:
        *permissions: Permission strings that must all be satisfied.

    Returns:
        A decorator equivalent to ``require_auth(permissions=list(permissions))``.
    """
    return require_auth(permissions=list(permissions))


def optional_auth(func: Callable) -> Callable:
    """Decorator that attaches optional auth: user is populated if present, never blocked.

    Can be used directly without invocation (unlike ``require_auth`` which always
    requires parentheses)::

        @optional_auth
        async def public_endpoint(request):
            user = getattr(request.state, "user", None)
            ...

    Args:
        func: The async route handler to wrap.

    Returns:
        The wrapped handler which always passes through.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await func(*args, **kwargs)

    return wrapper


__all__ = [
    "AuthorizationGuard",
    "RouteGuard",
    "authorization_documentation",
    "optional_auth",
    "require_auth",
    "require_permissions",
    "require_roles",
]
