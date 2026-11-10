"""Rate limiting middleware using Redis or CacheBackendProtocol.

Orchestrates the rate-limit strategies from
:mod:`quadkit.web.middleware.rate_limit_strategies` (sliding window,
token bucket, fixed window) behind the ``rate_limit`` decorator and
``RateLimitMiddleware`` ASGI middleware. Strategy classes are re-exported
here so the public import path is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import ContextVar, Token
from functools import wraps
import inspect
from typing import TYPE_CHECKING, Any, Literal

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.contracts.exceptions import RateLimitError
from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.logging import get_logger, safe_error_type
from quadkit.web.middleware.rate_limit_strategies import (
    CacheBackendLimiter as CacheBackendLimiter,
)
from quadkit.web.middleware.rate_limit_strategies import (
    MemoryLimiter as MemoryLimiter,
)
from quadkit.web.middleware.rate_limit_strategies import (
    RateLimiter as RateLimiter,
)
from quadkit.web.transport.responses import JSONResponse

if TYPE_CHECKING:
    from quadkit.web.config.rate_limit import RateLimitConfig

logger = get_logger(__name__)

_current_request_var: ContextVar[Request | None] = ContextVar(
    "quadkit_web_current_request",
    default=None,
)


def set_current_request(request: Request) -> Token[Request | None]:
    """Bind the active HTTP ``Request`` to the current async execution context."""
    return _current_request_var.set(request)


def reset_current_request(token: Token[Request | None]) -> None:
    """Restore the previous HTTP ``Request`` binding for the current context."""
    _current_request_var.reset(token)


def get_current_request() -> Request | None:
    """Return the active HTTP ``Request`` bound by the router, if any."""
    return _current_request_var.get()


def _is_asgi_request(candidate: Any) -> bool:
    """Return True if *candidate* looks like an HTTP Starlette/ASGI ``Request``."""
    scope = getattr(candidate, "scope", None)
    return (
        isinstance(scope, Mapping) and hasattr(candidate, "app") and "method" in scope
    )


def _limiter_supports_namespace(limiter: Any) -> bool:
    """Return True if ``limiter.check_rate_limit`` accepts ``namespace=...``."""
    if limiter is None:
        return False
    try:
        params = inspect.signature(limiter.check_rate_limit).parameters
        return "namespace" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
    except (TypeError, ValueError):
        return False


async def _resolve_container_limiter(request: Request) -> WebRateLimiterProtocol | None:
    """Resolve the ``WebRateLimiterProtocol`` bound by ``RateLimitModule``.

    Reads through the request-scoped container ``DIScopeMiddleware`` attaches
    to ``request.state`` (falling back to the root container), so that
    ``throttle()`` works ambiently when the module is registered — while
    apps without a limiter keep the warn-and-allow behaviour.
    """

    for container in (
        getattr(request.state, "container", None),
        getattr(request.state, "root_container", None),
    ):
        if container is None:
            continue
        try:
            resolver = getattr(container, "resolve", None)
            if resolver is None:
                continue
            limiter = resolver(WebRateLimiterProtocol)
            if inspect.isawaitable(limiter):
                limiter = await limiter
            if isinstance(limiter, WebRateLimiterProtocol):
                return limiter
        except Exception as exc:  # noqa: BLE001 — not bound in this app
            logger.debug(
                "rate_limit_container_resolution_miss",
                error_type=safe_error_type(exc),
            )
    return None


__all__ = [
    "CacheBackendLimiter",
    "MemoryLimiter",
    "RateLimitMiddleware",
    "RateLimiter",
    "get_current_request",
    "rate_limit",
    "reset_current_request",
    "set_current_request",
]


def _rate_limit_429_response(exc: Exception) -> JSONResponse:
    """Build the standard 429 response for a rate-limit breach.

    Args:
        exc: The :class:`~quadkit.contracts.exceptions.RateLimitError`.

    Returns:
        A 429 ``JSONResponse`` with a ``Retry-After`` header when the
        error carries a ``retry_after`` detail.
    """

    details = getattr(exc, "details", {}) or {}
    retry_after = details.get("retry_after")
    return JSONResponse(
        {"error": "rate_limit_exceeded", "message": str(exc)},
        status_code=429,
        headers={"Retry-After": str(retry_after)} if retry_after else {},
    )


def rate_limit(
    max_requests: int,
    window_seconds: int,
    scope: Literal["user", "ip", "endpoint"] = "user",
    limiter: WebRateLimiterProtocol | None = None,
) -> Callable:
    """Decorator for rate limiting endpoints.

    Enforces rate limits using the provided ``limiter`` instance (constructor
    injection). Explicit injection always wins.

    When no limiter is injected, the decorator resolves the
    :class:`~quadkit.contracts.web.WebRateLimiterProtocol` that
    :class:`~quadkit.web.RateLimitModule` binds in the container, through
    the request-scoped container on ``request.state``. If neither is
    available the endpoint executes without rate limiting and a warning is
    logged.

    Args:
        max_requests: Maximum requests per window.
        window_seconds: Time window in seconds.
        scope: Rate limit scope (user, ip, or endpoint).
        limiter: Required pre-constructed :class:`WebRateLimiterProtocol` instance.
            Must be injected at decoration time.

    Returns:
        Decorator function.

    Example:
        >>> my_limiter = RateLimiter(redis_client=redis)
        >>> @app.post("/api/upload")
        >>> @rate_limit(max_requests=5, window_seconds=60, limiter=my_limiter)
        >>> async def upload_file(request: Request):
        ...     return await process_upload()
    """
    _injected_limiter = limiter  # captured once at decoration time

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # ── 1. Locate the request object ───────────────────────────────
            request: Request | None = None
            for arg in args:
                if _is_asgi_request(arg):
                    request = arg
                    break
            if request is None:
                for val in kwargs.values():
                    if _is_asgi_request(val):
                        request = val
                        break
            if request is None:
                explicit_req = kwargs.get("request")
                if explicit_req is not None and _is_asgi_request(explicit_req):
                    request = explicit_req
            if request is None:
                request = get_current_request()

            if request is None:
                logger.warning(
                    "rate_limit_skipped_no_request",
                    endpoint=func.__name__,
                )
                return await func(*args, **kwargs)

            # ── 2. Resolve the limiter ─────────────────────────────────────
            # Explicit injection wins (constructor time, e.g. tests wiring
            # their own backend). Without it, fall back to the limiter the
            # RateLimitModule bound in the container for exactly this case —
            # it is read back through the request-scoped container that
            # DIScopeMiddleware attaches to request.state. When neither is
            # available, the historical behaviour stands: warn and allow.
            resolved_limiter: WebRateLimiterProtocol | None = _injected_limiter

            if resolved_limiter is None:
                resolved_limiter = await _resolve_container_limiter(request)

            if resolved_limiter is None:
                logger.warning(
                    "rate_limit_skipped_no_limiter",
                    endpoint=func.__name__,
                    reason="no limiter injected and no WebRateLimiterProtocol bound; "
                    "use rate_limit(limiter=...) or add RateLimitModule",
                )
                return await func(*args, **kwargs)

            # ── 3. Enforce the rate limit ───────────────────────────────────
            extra_kwargs: dict[str, Any] = {}
            if _limiter_supports_namespace(resolved_limiter):
                extra_kwargs["namespace"] = f"endpoint:{func.__qualname__}"
            await resolved_limiter.check_rate_limit(
                request=request,
                max_requests=max_requests,
                window_seconds=window_seconds,
                scope=scope,
                **extra_kwargs,
            )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimitMiddleware:
    """Middleware to add rate limit headers to all responses.

    Example:
        >>> app.add_middleware(RateLimitMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        rate_limiter: RateLimiter | None = None,
        config: RateLimitConfig | None = None,
    ) -> None:
        """Initialize middleware.

        Args:
            app: ASGI application.
            rate_limiter: Rate limiter instance (optional).
            config: ``RateLimitConfig`` driving per-path rules and defaults.
                When ``enabled`` and a limiter is present, ``__call__``
                enforces the matched rule (or the default limit) instead of
                only stamping headers.
        """
        self.app = app
        self.rate_limiter = rate_limiter
        self.config = config
        self._supports_namespace = _limiter_supports_namespace(rate_limiter)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process request and add rate limit headers.

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ── Enforce before forwarding ─────────────────────────────────────
        # The existing check_rate_limit() algorithm (Redis Lua / cache /
        # in-memory) is the single enforcement engine. A breached request
        # gets the standard 429 + Retry-After response (RateLimitError is
        # caught here because middleware raises bypass Starlette's inner
        # ExceptionMiddleware on supported versions and would surface as 500).
        if (
            self.rate_limiter is not None
            and self.config is not None
            and self.config.enabled
        ):
            request = Request(scope, receive)
            if (
                self.config.whitelist_ips
                and request.client
                and request.client.host in self.config.whitelist_ips
            ):
                pass  # whitelisted — skip enforcement (D2)
            else:
                matched = self.config.get_matched_rule(request.url.path)
                namespace: str | None = None
                if matched is not None:
                    pattern, rule = matched
                    max_requests, window_seconds = rule.requests, rule.window
                    namespace = f"rule:{pattern}"
                else:
                    max_requests = self.config.default_limit
                    window_seconds = self.config.default_window
                try:
                    if namespace is not None and self._supports_namespace:
                        await self.rate_limiter.check_rate_limit(
                            request,
                            max_requests=max_requests,
                            window_seconds=window_seconds,
                            scope="user",
                            namespace=namespace,
                        )
                    else:
                        await self.rate_limiter.check_rate_limit(
                            request,
                            max_requests=max_requests,
                            window_seconds=window_seconds,
                            scope="user",
                        )
                except RateLimitError as exc:
                    response = _rate_limit_429_response(exc)
                    await response(scope, receive, send)
                    return

        async def send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Add rate limit headers if available (stored in request.state)
                # scope["state"] is a plain dict in Starlette; State is a wrapper
                state = scope.get("state")
                if isinstance(state, dict):
                    remaining = state.get("rate_limit_remaining")
                    limit = state.get("rate_limit_limit")
                    reset = state.get("rate_limit_reset")
                elif state is not None:
                    remaining = getattr(state, "rate_limit_remaining", None)
                    limit = getattr(state, "rate_limit_limit", None)
                    reset = getattr(state, "rate_limit_reset", None)
                else:
                    remaining = limit = reset = None

                if remaining is not None:
                    headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                if limit is not None:
                    headers.append((b"x-ratelimit-limit", str(limit).encode()))
                if reset is not None:
                    headers.append((b"x-ratelimit-reset", str(reset).encode()))

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
