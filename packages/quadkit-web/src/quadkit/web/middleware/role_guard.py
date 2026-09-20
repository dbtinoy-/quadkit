"""Role guard middleware — declarative path-to-role enforcement.

Guards HTTP paths against configured role requirements using the
authenticated identity set by the authentication middleware
(``scope["state"]["user_id"]``). Roles are resolved **per request** from the
identity store (never from JWT claims), so demotions take effect immediately.

Rules are plain values: an exact path, or a path ending in ``/**`` which
matches every path under that prefix. The first matching rule wins.

Registration order matters: this middleware must sit **inside** the
authentication middleware so an authenticated identity exists when it runs.
In :class:`~quadkit.web.di.provider.WebProvider` the auth middleware is
registered by :class:`~quadkit.web.integrations.auth.AuthIntegration`; the
role guard is registered right after it in the same step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RoleGuardRule:
    """One role guard rule.

    Attributes:
        path: Exact path to guard. A trailing ``/**`` matches every path
            under that prefix (e.g. ``/api/admin/**`` also matches
            ``/api/admin`` itself).
        roles: Role identifiers allowed to pass.
    """

    path: str
    roles: list[str]


@runtime_checkable
class RoleResolverProtocol(Protocol):
    """Resolve the role set of the authenticated user per request.

    Implementations must query the identity store — never read JWT claims —
    so demotions take effect immediately.
    """

    async def resolve(self, user_id: str) -> list[str] | None:
        """Return the roles granted to *user_id*.

        Args:
            user_id: Verified identity of the authenticated caller.

        Returns:
            The roles granted to the user, or ``None`` when the user is
            unknown or deactivated.
        """
        ...


class RoleGuardMiddleware:
    """ASGI middleware enforcing role rules against authenticated identities.

    Args:
        app: Inner ASGI application.
        rules: Rules applied in declaration order; first match wins.
        resolver: Per-request role resolver.
    """

    def __init__(
        self,
        app: ASGIApp,
        rules: list[RoleGuardRule],
        resolver: RoleResolverProtocol,
    ) -> None:
        """Initialise the middleware with its rule set and resolver.

        Args:
            app: Inner ASGI application.
            rules: Rules applied in declaration order; first match wins.
            resolver: Per-request role resolver.
        """
        self.app = app
        self._rules = rules
        self._resolver = resolver

    def _match(self, path: str) -> RoleGuardRule | None:
        """Return the first rule matching *path*.

        Args:
            path: Request path to evaluate.

        Returns:
            The first matching rule, or ``None`` when no rule applies.
        """
        for rule in self._rules:
            if rule.path.endswith("/**"):
                prefix = rule.path[:-3].rstrip("/")
                if path == prefix or path.startswith(f"{prefix}/"):
                    return rule
            elif path == rule.path:
                return rule
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce role rules for the request.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rule = self._match(scope.get("path", ""))
        if rule is None:
            await self.app(scope, receive, send)
            return

        user_id = scope.setdefault("state", {}).get("user_id")
        if user_id is None:
            logger.warning("role_guard_unauthorized", path=scope.get("path"))
            await self._reject(scope, receive, send, 401, "Unauthorized")
            return

        roles = await self._resolver.resolve(str(user_id))
        if roles is None or not set(roles).intersection(rule.roles):
            logger.warning(
                "role_guard_forbidden",
                path=scope.get("path"),
                user_id=str(user_id),
                rule_roles=list(rule.roles),
            )
            await self._reject(scope, receive, send, 403, "Forbidden")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        error: str,
    ) -> None:
        """Respond with a JSON error body.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
            status_code: HTTP status of the rejection.
            error: Error message for the ``{"error": ...}`` body.
        """
        response = JSONResponse({"error": error}, status_code=status_code)
        await response(scope, receive, send)


__all__ = [
    "RoleGuardMiddleware",
    "RoleGuardRule",
    "RoleResolverProtocol",
]
