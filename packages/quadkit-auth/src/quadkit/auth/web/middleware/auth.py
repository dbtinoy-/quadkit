"""Authentication middleware for web applications"""

from __future__ import annotations

from functools import wraps
import hashlib
from typing import TYPE_CHECKING, Any, cast

from quadkit.auth.config import AuthMiddlewareConfig
from quadkit.auth.constants import AUTH_LOGIN_PATH, AUTH_REGISTER_PATH
from quadkit.logging import get_logger
from quadkit.primitives.context import USER_ID, Context

#: Auth endpoints that are always throttled, whether or not they are excluded
#: from authentication. ``/auth/login`` is both the canonical excluded path —
#: it has to be reachable without a credential, which is why it is in
#: ``DEFAULT_EXCLUDED_PATHS`` — and the one endpoint an attacker can hammer, so
#: excluding it from *authentication* must never exclude it from throttling.
RATE_LIMITED_PATHS: tuple[str, ...] = (AUTH_LOGIN_PATH, AUTH_REGISTER_PATH)

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.auth.authn.services import LoginAttemptTracker
    from quadkit.auth.models.user import User
    from quadkit.contracts import AuthProviderProtocol
    from quadkit.contracts.web import RequestProtocol as Request

from datetime import UTC

# Re-export guards for convenience
from quadkit.auth.authz.guards import optional_auth, require_permissions, require_roles
from quadkit.auth.web.middleware.api_key_authenticator import ApiKeyAuthenticator
from quadkit.auth.web.middleware.jwt_authenticator import JwtAuthenticator
from quadkit.auth.web.middleware.response_handler import AuthResponseHandler
from quadkit.auth.web.middleware.session_authenticator import SessionAuthenticator
from quadkit.auth.web.middleware.session_validator import SessionValidator
from quadkit.auth.web.middleware.throttle import RateLimitMiddleware
from quadkit.auth.web.middleware.token_cache import TokenCache
from quadkit.auth.web.middleware.token_extractor import TokenExtractor

logger = get_logger(__name__)


class AuthMiddleware:
    """Middleware for handling authentication and authorization - Pure ASGI implementation."""

    def __init__(
        self,
        auth_provider: AuthProviderProtocol,
        config: AuthMiddlewareConfig | None = None,
        ctx: Context | None = None,
        attempt_tracker: LoginAttemptTracker | None = None,
    ):
        self.auth_provider = auth_provider
        self.config = config or AuthMiddlewareConfig()
        self._ctx = ctx

        # Initialize extracted components
        self.token_extractor = TokenExtractor(self.config)
        self.session_validator = SessionValidator(self.config, self.auth_provider)
        self.token_cache = TokenCache()
        self.api_key_authenticator = ApiKeyAuthenticator(self.auth_provider)
        self.session_authenticator = SessionAuthenticator(self.auth_provider)
        self.jwt_authenticator = JwtAuthenticator(self.auth_provider)
        self.response_handler = AuthResponseHandler()

        self.attempt_tracker = attempt_tracker

        # Initialize Rate Limiter
        cache_service = getattr(self.auth_provider, "cache_service", None)
        # Safely extract rate_limit value (avoid accessing Field descriptor)
        rate_limit_val = getattr(self.config, "login_rate_limit", None)
        if not isinstance(rate_limit_val, str):
            rate_limit_val = "5/minute"
        self.rate_limiter = RateLimitMiddleware(
            app=None,  # Will be managed manually
            cache_service=cache_service,
            rate_limit=rate_limit_val,
        )

    def should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for this path"""
        return self.session_validator.should_skip_auth(path)

    def extract_token(self, request: Request) -> str | None:
        """Extract authentication token from request"""
        return self.token_extractor.extract_token(request)

    async def authenticate_request(self, request: Any) -> User | None:
        """Authenticate the request and return user if valid"""
        token = self.extract_token(request)
        if not token:
            logger.info("AuthMiddleware.authenticate_request: no token extracted")
            return None

        # Check lockout before doing any authentication work
        if self.attempt_tracker is not None:
            client_ip = getattr(getattr(request, "client", None), "host", token)
            if await self.attempt_tracker.is_locked(client_ip):
                logger.warning(
                    "AuthMiddleware.authenticate_request: client locked out",
                    extra={"client_ip": client_ip},
                )
                return None

        # Check token cache first (avoid JWT decode + DB lookup)
        cached_user = await self.token_cache.get(token)
        if cached_user:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            logger.info(
                "AuthMiddleware.authenticate_request: Token cache HIT for token_hash=%s",
                token_hash[:10],
            )
            return cast("User | None", cached_user)

        # Try API key authentication
        user = await self.api_key_authenticator.authenticate(token, request)
        if user:
            await self.token_cache.set(token, user)
            return cast("User | None", user)

        # Try session authentication
        user = await self.session_authenticator.authenticate(request)
        if user:
            return cast("User | None", user)

        # Try JWT authentication — the authenticator now extracts the token
        # from the request internally (signature changed in an earlier refactor).
        user = await self.jwt_authenticator.authenticate(request)
        if user:
            await self.token_cache.set(token, user)

        # Record failed attempt when all authenticators returned None
        if user is None and self.attempt_tracker is not None:
            client_ip = getattr(getattr(request, "client", None), "host", token)
            await self.attempt_tracker.record_failure(client_ip)
            logger.debug(
                "AuthMiddleware.authenticate_request: recorded failed attempt",
                extra={"client_ip": client_ip},
            )

        return cast("User | None", user)

    def check_authorization(self, user: User) -> bool:
        """Check if user is authorized based on roles/permissions"""
        return self.session_validator.check_authorization(user)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        """Pure ASGI middleware entry point - OPT-AUTH-2."""
        # Only handle HTTP requests
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # ASGI framework-binding layer: StarletteRequest constructs a request
        # from the raw ASGI scope/receive callables. This is intentionally
        # Starlette-specific — it cannot be replaced with RequestProtocol,
        # which is a structural protocol for type annotations only.
        from starlette.requests import Request as StarletteRequest

        request = StarletteRequest(scope, receive)

        # Skip authentication for excluded paths. Throttling still applies:
        # the excluded defaults include `/auth/login`, and letting the
        # short-circuit swallow the limiter would disable brute-force
        # protection on exactly the endpoint that needs it most.
        logger.debug("AuthMiddleware: checking path=%s", request.url.path)
        if self.should_skip_auth(request.url.path):
            if request.url.path in RATE_LIMITED_PATHS:
                self.rate_limiter.app = self.app
                await self.rate_limiter(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        # Skip authentication for OPTIONS method (CORS preflight)
        logger.debug(
            "AuthMiddleware: method=%s, path=%s", request.method, request.url.path
        )
        if request.method == "OPTIONS":
            logger.debug("AuthMiddleware: skipping auth for OPTIONS request")
            await self.app(scope, receive, send)
            return

        # Authenticate request
        user = await self.authenticate_request(request)

        # Store user in scope (Starlette style)
        scope["user"] = user

        # Initialize state dict if not present
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["user"] = user
        scope["state"]["user_id"] = str(user.user_id) if user is not None else None

        # Store user in runtime context for unified access across HTTP/WebSocket/Tasks
        from quadkit.di.resolution.context import get_resolver

        resolver = get_resolver(scope)
        if resolver and self._ctx is not None and user is not None:
            self._ctx.set(USER_ID, str(user.user_id))

        # Apply Rate Limiting for auth endpoints
        if request.url.path in RATE_LIMITED_PATHS:
            # We use the raw ASGI call pattern to integrate it
            # But we need a 'send' that we can wrap if we want to detect success
            # For now, let's keep it simple: just call it.
            # However, RateLimitMiddleware expects app to be a callable.
            # We can just delegate to our app if allowed.

            # Re-usable wrapper to continue if not throttled
            async def next_app(s: dict[str, Any], r: Any, sn: Any) -> Any:
                await self.app(s, r, sn)

            # Temporarily set app and call
            self.rate_limiter.app = next_app
            await self.rate_limiter(scope, receive, send)
            return

        # Check authorization if user is required
        if (
            not self.config.optional_auth
            or self.config.roles_required
            or self.config.permissions_required
        ):
            if not user:
                # No user but auth is required
                response = await self.response_handler.unauthorized_response(
                    "Authentication required",
                    request=request,
                )
                await response(scope, receive, send)
                return

            if not self.check_authorization(user):
                # User doesn't have required roles/permissions
                response = await self.response_handler.forbidden_response(
                    "Insufficient permissions",
                )
                await response(scope, receive, send)
                return

        # Continue with request - capture response to add headers
        response_started = False
        response_headers = []

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_started, response_headers
            if message.get("type") == "http.response.start":
                response_started = True
                response_headers = list(message.get("headers", []))
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def set_app(self, app: Callable) -> None:
        """Set the ASGI app to wrap."""
        self.app = app


# RateLimitMiddleware has been moved to quadkit.auth.web.middleware.throttle


class AuthRouter:
    """Router extension with authentication helpers"""

    def __init__(self, auth_provider: AuthProviderProtocol):
        self.auth_provider = auth_provider

    def require_auth(
        self,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        optional: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to require authentication and authorization for routes"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                request = _extract_request(*args, **kwargs)

                if not request:
                    raise ValueError(
                        "Could not find request object in function arguments",
                    )

                # Check authentication
                user = getattr(request.state, "user", None)
                if not optional and not user:
                    rf = await _get_response_factory(request)

                    return rf.json(
                        status_code=401,
                        content={
                            "error": "unauthorized",
                            "message": "Authentication required",
                        },
                    )

                # Check authorization
                if user:
                    if roles and not self.auth_provider.has_any_role(user, roles):
                        rf = await _get_response_factory(request)

                        return rf.json(
                            status_code=403,
                            content={
                                "error": "forbidden",
                                "message": "Insufficient roles",
                            },
                        )

                    if permissions and not self.auth_provider.has_any_permission(
                        user,
                        permissions,
                    ):
                        rf = await _get_response_factory(request)

                        return rf.json(
                            status_code=403,
                            content={
                                "error": "forbidden",
                                "message": "Insufficient permissions",
                            },
                        )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get_current_user(self, request: Request) -> User | None:
        """Get current authenticated user from request"""
        return getattr(request.state, "user", None)


# Convenience helpers and functions for common auth patterns


def _extract_request(*args: Any, **kwargs: Any) -> Any:
    """Extract the Starlette-like request object from positional or keyword args."""
    for arg in args:
        if hasattr(arg, "state") and hasattr(arg, "headers"):
            return arg
    return kwargs.get("request")


async def _get_auth_provider(context: Any | None = None) -> AuthProviderProtocol:
    """Resolve `AuthProvider` from dynamic context or global container."""
    from quadkit.contracts.auth import AuthProviderProtocol
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if not resolver:
        raise RuntimeError(
            "No DI resolver found in current context. Ensure application is initialized.",
        )

    return cast("AuthProviderProtocol", await resolver.resolve(AuthProviderProtocol))


async def _get_response_factory(context: Any | None = None) -> Any:
    """Resolve `ResponseFactoryProtocol` from global container."""
    from quadkit.contracts.web import ResponseFactoryProtocol
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if not resolver:
        return None

    return await resolver.resolve(ResponseFactoryProtocol)


def require_mfa(
    max_age_seconds: int = 300,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to require MFA verification (step-up).

    Ensures:
    1. User has MFA enabled.
    2. Session was verified with MFA within the last `max_age_seconds`.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _extract_request(*args, **kwargs)
            if not request:
                return await func(*args, **kwargs)

            user = getattr(request.state, "user", None)
            if not user:
                rf = await _get_response_factory(request)
                return rf.json(status_code=401, content={"error": "unauthorized"})

            # Resolve AuthProvider/MFAManager
            auth_provider = await _get_auth_provider(request)
            if auth_provider.mfa_manager:
                mfa = await auth_provider.mfa_manager.get_mfa(user.user_id)
                if not mfa or not mfa.is_enabled:
                    rf = await _get_response_factory(request)

                    return rf.json(
                        status_code=403,
                        content={
                            "error": "mfa_required",
                            "message": "MFA must be enabled for this operation",
                        },
                    )

                # Check session step-up status
                session = getattr(request.state, "session", None)
                is_verified = False
                if session and session.mfa_verified_at:
                    from datetime import datetime

                    age = (
                        datetime.now(UTC) - session.mfa_verified_at.replace(tzinfo=UTC)
                    ).total_seconds()
                    if age < max_age_seconds:
                        is_verified = True

                if not is_verified:
                    rf = await _get_response_factory(request)

                    return rf.json(
                        status_code=401,
                        content={
                            "error": "mfa_verification_required",
                            "message": "Step-up authentication required",
                            "stepup_url": "/api/v1/auth/mfa/verify",
                        },
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "AuthMiddleware",
    "AuthMiddlewareConfig",
    "AuthRouter",
    "logger",
    "optional_auth",
    "require_mfa",
    "require_permissions",
    "require_roles",
]
