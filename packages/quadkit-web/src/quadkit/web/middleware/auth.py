"""Authentication middleware base.

This module provides HTTP transport layer authentication middleware.
Authentication logic (JWT, OAuth2, etc.) is implemented in quadkit-auth package.

Architecture:
- quadkit-web: HTTP transport (middleware, headers, cookies)
- quadkit-auth: Security logic (JWT decoding, password hashing, OAuth flows)
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.contracts.auth import IdentityResolverProtocol
from quadkit.contracts.auth.guard import (
    AuthenticatorProtocol,
    AuthorizerProtocol,
)
from quadkit.contracts.exceptions import (
    AuthenticationError as QuadkitAuthenticationError,
)
from quadkit.contracts.exceptions import (
    AuthorizationError as QuadkitAuthorizationError,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthenticationMiddleware:
    """HTTP transport layer authentication middleware.

    This middleware handles the HTTP transport aspects of authentication:
    - Extracting credentials from HTTP headers/cookies
    - Setting user in request state
    - Returning 401 Unauthorized responses
    - Optionally resolving OAuth external IDs to internal UUIDs

    The actual authentication logic (JWT decoding, password validation, etc.)
    is delegated to AuthenticatorProtocol implementations.

    Example:
        from quadkit.web.middleware.auth import AuthenticationMiddleware

        # Authenticators are injected or created elsewhere
        jwt_auth = ...  # Some AuthenticatorProtocol implementation
        middleware = AuthenticationMiddleware(authenticators=[jwt_auth])
    """

    def __init__(
        self,
        app: ASGIApp,
        authenticators: list[AuthenticatorProtocol] | None = None,
        authorizer: AuthorizerProtocol | None = None,
        exclude_paths: list[str] | None = None,
        enable_identity_resolution: bool = False,
        identity_resolver: IdentityResolverProtocol | None = None,
    ):
        """Initialize authentication middleware.

        Args:
            app: ASGI application
            authenticators: List of authenticators implementing AuthenticatorProtocol protocol
            authorizer: Optional authorizer implementing AuthorizerProtocol protocol
            exclude_paths: Paths to skip authentication (e.g., ['/health', '/docs'])
            enable_identity_resolution: Whether to resolve OAuth external IDs to internal UUIDs
            identity_resolver: Optional resolver for OAuth identity resolution
        """
        self.app = app
        self.authenticators = authenticators or []  # Allow empty list
        self.authorizer = authorizer
        self.exclude_paths = exclude_paths or []
        self.enable_identity_resolution = enable_identity_resolution
        self.identity_resolver = identity_resolver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate the request using configured authenticators."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get path from scope
        path = scope.get("path", "")

        # Determine if authentication is mandatory for this path
        is_excluded = any(
            path.startswith(excl_path) for excl_path in self.exclude_paths
        )

        # Create request from scope for authenticators
        request = Request(scope)

        # Try each authenticator in order
        user = None
        if self.authenticators:
            for authenticator in self.authenticators:
                user = await authenticator.authenticate(request)
                if user is not None:
                    break

        # If no authenticators are configured, allow request through without authentication
        if not self.authenticators:
            await self.app(scope, receive, send)
            return

        if user is None and not is_excluded:
            # Emit structured audit log for auth failure
            client_host = scope.get("client", ("unknown", 0))[0]
            method = scope.get("method", b"")
            method_str = method.decode() if isinstance(method, bytes) else str(method)
            logger.warning(
                "security.auth_failure",
                path=path,
                method=method_str,
                client_ip=client_host,
                reason="no_authenticator_succeeded",
            )
            # Send 401 response
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                },
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "Authentication required"}',
                },
            )
            return

        # Optionally resolve OAuth external IDs to internal UUIDs
        if (
            self.enable_identity_resolution
            and self.identity_resolver is not None
            and user is not None
        ):

            def _get(obj: object, key: str, default: object = None) -> object:
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            user_id = _get(user, "id") or _get(user, "user_id")
            provider = _get(user, "provider") or "google"

            resolved_id = await self.identity_resolver.resolve_user_id(
                user_id,  # type: ignore[arg-type]
                provider,  # type: ignore[arg-type]
            )
            if resolved_id:
                if isinstance(user, dict):
                    user_dict: dict = {**user}
                else:
                    user_dict = dict(user)
                user_dict["id"] = resolved_id
                user_dict["user_id"] = resolved_id
                user_dict["resolved"] = True
                user = user_dict

        # Normalise user to dict
        if user is not None and not isinstance(user, dict):
            if isinstance(user, bool):
                user = None
            elif hasattr(user, "model_dump") and callable(user.model_dump):
                user = user.model_dump()
            elif hasattr(user, "__dict__"):
                import dataclasses

                if dataclasses.is_dataclass(user):
                    user = dataclasses.asdict(user)  # type: ignore[arg-type]
                else:
                    user = dict(vars(user))
            else:
                try:
                    user = dict(user)
                except (TypeError, ValueError):
                    user = None

        # Store user in scope state
        scope.setdefault("state", {})["user"] = user

        # Extract and stringify user_id
        uid = user.get("id") or user.get("user_id") if user else None
        if uid is not None:
            uid = str(uid)

        scope.setdefault("state", {})["user_id"] = uid

        # Also store in scope extensions
        scope.setdefault("extensions", {})["user"] = user
        scope.setdefault("extensions", {})["user_id"] = uid

        # Continue with request
        await self.app(scope, receive, send)


AuthenticationError = QuadkitAuthenticationError
AuthorizationError = QuadkitAuthorizationError
