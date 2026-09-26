from __future__ import annotations

from collections.abc import Callable
import functools
from typing import Any, TypeVar

from quadkit.auth.exceptions import AuthenticationError, AuthorizationError

F = TypeVar("F", bound=Callable[..., Any])


def _extract_request(*args: Any, **kwargs: Any) -> Any:
    """Extract the request-like object from positional or keyword args."""
    for arg in args:
        if hasattr(arg, "identity") or hasattr(arg, "state"):
            return arg
    return kwargs.get("request")


def require_auth(fn: F) -> F:
    """Require a valid authenticated identity on the request context.

    The decorator reads ``request.identity`` from the first positional argument
    (assumed to be the request/context object). Raises ``AuthenticationError``
    when no identity is present.

    Args:
        fn: The async handler function to decorate.

    Returns:
        Decorated async handler that validates identity before invocation.

    Raises:
        AuthenticationError: When no identity is present on the request.

    Example::

        @require_auth
        async def get_profile(self, request: Request) -> Response:
            return Response(data=request.identity.claims)
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = _extract_request(*args, **kwargs)
        if request is None or not getattr(request, "identity", None):
            raise AuthenticationError("Authentication required")
        return await fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_roles(*roles: str) -> Callable[[F], F]:
    """Require that the authenticated identity holds at least one of the given roles.

    Args:
        *roles: One or more role names. Access is granted if the identity
            has **any** of the listed roles.

    Returns:
        Decorator that enforces role-based access control.

    Raises:
        AuthenticationError: When no identity is present on the request.
        AuthorizationError: When the identity lacks all required roles.

    Example::

        @require_roles("admin", "moderator")
        async def delete_post(self, request: Request, post_id: str) -> Response: ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _extract_request(*args, **kwargs)
            identity = (
                getattr(request, "identity", None) if request is not None else None
            )
            if identity is None:
                raise AuthenticationError("Authentication required")
            identity_roles: set[str] = set(getattr(identity, "roles", []))
            if not identity_roles.intersection(roles):
                raise AuthorizationError(
                    f"Required roles: {roles!r}. Identity has: {sorted(identity_roles)!r}"
                )
            return await fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["require_auth", "require_roles"]
