"""Authentication middleware base.

This module provides HTTP transport layer authentication middleware.
Authentication logic (JWT, OAuth2, etc.) is implemented in quadkit-auth package.

Architecture:
- quadkit-web: HTTP transport (middleware, headers, cookies)
- quadkit-auth: Security logic (JWT decoding, password hashing, OAuth flows)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def _normalise_user(user: object) -> dict | None:
    """Convert supported identity values before deciding authentication succeeded."""
    if user is None or isinstance(user, bool):
        return None
    if isinstance(user, dict):
        result = user
    elif hasattr(user, "model_dump") and callable(user.model_dump):
        result = user.model_dump()
    elif hasattr(user, "__dict__"):
        import dataclasses

        result = (
            dataclasses.asdict(user)  # type: ignore[arg-type]
            if dataclasses.is_dataclass(user)
            else dict(vars(user))
        )
    else:
        try:
            result = dict(user)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None
    # An empty object cannot identify a principal. Do not let it bypass this
    # middleware or suppress later authenticators in the configured chain.
    return result if isinstance(result, dict) and result else None


@dataclass(frozen=True, slots=True)
class AuthenticationMiddlewareDocumentation:
    """Native mandatory-auth rejection claim after successful middleware setup.

    No bearer/cookie scheme is inferred from the authenticator protocol. Exclusions
    use this middleware's literal prefix matching, not router/group semantics.
    Empty-authenticator middleware must not publish this claim.
    """

    exclude_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.exclude_paths) is not tuple or any(
            not isinstance(prefix, str) for prefix in self.exclude_paths
        ):
            raise ValueError("Invalid authentication middleware exclusions")

    def responses_for(self, path: str) -> dict[str, Any]:
        """Describe the native error-only branch without authenticating a request."""
        # Documentation paths are templates. Only a prefix wholly inside the
        # fixed leading text exempts every concrete request. Variable names
        # are not literal runtime values; narrower exclusions can exempt some
        # values without removing the operation's possible401 response.
        literal_prefix = path.partition("{")[0]
        if any(literal_prefix.startswith(prefix) for prefix in self.exclude_paths):
            return {}
        return {
            "401": {
                "description": "Authentication required.",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "string",
                                    "enum": ["Authentication required"],
                                },
                            },
                            "required": ["error"],
                        },
                    },
                },
            },
        }


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

    def _is_path_excluded(self, method: str, path: str) -> bool:
        """Check whether *method* + *path* matches any configured exclusion rule.

        Entries in ``exclude_paths`` may be plain path prefixes (e.g. ``"/health"``,
        or ``"/"`` for exact root) or HTTP-method-qualified prefixes such as
        ``"GET /api/v1/media/"`` so public read endpoints can coexist under a
        shared prefix with authenticated write routes.
        """
        upper_method = method.upper()
        for raw_rule in self.exclude_paths:
            if " " in raw_rule:
                rule_method, excl_path = raw_rule.split(" ", 1)
                if rule_method.strip().upper() != upper_method:
                    continue
                excl_path = excl_path.strip()
            else:
                excl_path = raw_rule
            if path == "/" if excl_path == "/" else path.startswith(excl_path):
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate the request using configured authenticators."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get path and method from scope
        path = scope.get("path", "")
        raw_method = scope.get("method", b"")
        method_str = (
            raw_method.decode() if isinstance(raw_method, bytes) else str(raw_method)
        )

        # Determine if authentication is mandatory for this path
        is_excluded = self._is_path_excluded(method_str, path)

        # Create request from scope for authenticators
        request = Request(scope)

        # Try each authenticator in order
        user = None
        if self.authenticators:
            for authenticator in self.authenticators:
                user = _normalise_user(await authenticator.authenticate(request))
                if user is not None:
                    break

        # If no authenticators are configured, allow request through without authentication
        if not self.authenticators:
            await self.app(scope, receive, send)
            return

        if user is None and not is_excluded:
            # Emit structured audit log for auth failure
            client_host = scope.get("client", ("unknown", 0))[0]
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

        # Normalise user to dict before optional OAuth identity resolution
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

        # Optionally resolve OAuth external IDs to internal UUIDs
        if (
            self.enable_identity_resolution
            and self.identity_resolver is not None
            and user is not None
        ):
            user_id = str(user.get("id") or user.get("user_id") or "")
            provider = str(user.get("provider") or "google")

            resolved_id = await self.identity_resolver.resolve_user_id(
                user_id,
                provider,
            )
            if resolved_id:
                user_dict: dict = {**user}
                user_dict["id"] = resolved_id
                user_dict["user_id"] = resolved_id
                user_dict["resolved"] = True
                user = user_dict

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
