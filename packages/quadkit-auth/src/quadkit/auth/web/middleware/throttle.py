"""Rate-limiting middleware for authentication endpoints.

Provides in-memory IP-based rate limiting targeted at brute-force-prone
auth endpoints (``/auth/login``, ``/auth/register``, etc.).

Typical usage::

    app = RateLimitMiddleware(app, rate_limit="5/minute", block_duration=300)
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from quadkit import serialization as _json
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from collections.abc import Callable

# Endpoints to which rate limiting is applied.
_RATE_LIMITED_PATHS: frozenset[str] = frozenset(
    {
        "/auth/login",
        "/auth/register",
        "/auth/token",
        "/auth/refresh",
        "/auth/password-reset",
    }
)


class RateLimitExceededError(Exception):
    """Raised when a client has exceeded the configured rate limit.

    Carries ``retry_after`` (seconds) so callers can propagate the value in
    a ``Retry-After`` response header.
    """

    _code = "QK_ERR_SEC_012"

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s.")
        self.retry_after = retry_after


def _parse_rate_limit(rate_limit: str) -> tuple[int, int]:
    """Parse a rate-limit string such as ``"5/minute"`` into ``(max, seconds)``.

    Supported periods: ``second`` / ``seconds``, ``minute`` / ``minutes``,
    ``hour`` / ``hours``.

    Args:
        rate_limit: A string in the form ``"<count>/<period>"``.

    Returns:
        A ``(max_requests, window_seconds)`` tuple.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    try:
        count_str, period = rate_limit.split("/", maxsplit=1)
        count = int(count_str.strip())
        period = period.strip().lower()
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            f"Invalid rate_limit format {rate_limit!r}. "
            "Expected '<count>/<period>', e.g. '5/minute'."
        ) from exc

    _period_map: dict[str, int] = {
        "second": 1,
        "seconds": 1,
        "minute": 60,
        "minutes": 60,
        "hour": 3600,
        "hours": 3600,
    }
    if period not in _period_map:
        raise ValueError(
            f"Unknown period {period!r}. "
            f"Supported values: {', '.join(sorted(_period_map))}."
        )
    return count, _period_map[period]


class RateLimitMiddleware:
    """ASGI middleware that rate-limits authentication endpoints.

    Applies a sliding-window rate limit to requests whose ``path`` matches
    a known auth endpoint.  Clients that exceed the limit receive a ``429``
    response and are blocked for *block_duration* seconds.  Successful
    responses (HTTP 2xx) clear the attempt history for the client.

    Args:
        app: The next ASGI application in the chain.
        rate_limit: Rate-limit string, e.g. ``"5/minute"``.
        block_duration: How long (seconds) a client remains blocked after
            exceeding the limit.  Defaults to ``60``.
        paths: Optional set of URL paths to which rate limiting is applied.
            Falls back to the built-in :data:`_RATE_LIMITED_PATHS` set.
    """

    def __init__(
        self,
        app: Any,
        rate_limit: str = "5/minute",
        block_duration: int = 60,
        paths: frozenset[str] | None = None,
        cache_service: Any | None = None,
    ) -> None:
        self.app = app
        self.block_duration = block_duration
        self._paths = paths if paths is not None else _RATE_LIMITED_PATHS
        # Optional external cache (e.g. Redis) for distributed rate limiting.
        # Not used in the built-in in-memory implementation; reserved for
        # future Redis-backed backends.
        self.cache_service = cache_service

        max_requests, window_seconds = _parse_rate_limit(rate_limit)
        self._max_requests = max_requests
        self._window_seconds = window_seconds

        # Mutable state exposed for tests
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.blocked: dict[str, float] = {}

    # ------------------------------------------------------------------
    # ASGI interface
    # ------------------------------------------------------------------

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """Process an ASGI request."""
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if path not in self._paths:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_id: str = client[0] if client else "unknown"

        # --- get current time ---
        now = ambient_clock.monotonic()

        # --- check / enforce block ---
        if client_id in self.blocked:
            unblock_at = self.blocked[client_id]
            remaining = int(unblock_at - now)
            if remaining > 0:
                await self._send_429(send, remaining)
                return
            # Block expired — release
            del self.blocked[client_id]

        # --- sliding-window check ---
        cutoff = now - self._window_seconds
        self.attempts[client_id] = [t for t in self.attempts[client_id] if t > cutoff]
        if len(self.attempts[client_id]) >= self._max_requests:
            # Block the client and respond 429
            self.blocked[client_id] = now + self.block_duration
            await self._send_429(send, self.block_duration)
            return

        # --- record this attempt and delegate to next app ---
        self.attempts[client_id].append(now)

        # Wrap send so we can inspect the response status code
        response_status: list[int] = []

        async def intercepting_send(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                response_status.append(message.get("status", 0))
            await send(message)

        await self.app(scope, receive, intercepting_send)

        # On a successful response, clear the attempt counter
        if response_status and 200 <= response_status[0] < 300:
            self.attempts[client_id] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_429(send: Any, retry_after: int) -> None:
        """Send a 429 Too Many Requests ASGI response."""
        body = _json.dumps(
            {
                "detail": "Too many requests. Please try again later.",
                "retry_after": retry_after,
            }
        )
        retry_bytes = str(retry_after).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", retry_bytes),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


def throttle(
    rate_limit: str = "5/minute",
    block_duration: int = 60,
    paths: frozenset[str] | None = None,
) -> Callable[[Any], RateLimitMiddleware]:
    """Decorator / factory that wraps an ASGI app with :class:`RateLimitMiddleware`.

    Can be used as a decorator::

        @throttle(rate_limit="10/minute")
        async def app(scope, receive, send): ...

    Args:
        rate_limit: Rate-limit string, e.g. ``"5/minute"``.
        block_duration: Block duration in seconds.
        paths: URL paths to rate-limit (defaults to built-in auth paths).

    Returns:
        A callable that wraps an ASGI app with the configured middleware.
    """

    def decorator(app: Any) -> RateLimitMiddleware:
        return RateLimitMiddleware(
            app,
            rate_limit=rate_limit,
            block_duration=block_duration,
            paths=paths,
        )

    return decorator


__all__ = [
    "RateLimitExceededError",
    "RateLimitMiddleware",
    "throttle",
]
