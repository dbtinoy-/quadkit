"""@throttle decorator and RateLimitModule — ergonomic rate limiting sugar.

Provides a NestJS-style ``@throttle("30/minute")`` decorator that sits on top
of the lower-level :func:`~quadkit.web.middleware.rate_limit.rate_limit`
decorator, plus a ``RateLimitModule`` for module-level configuration.

Usage::

    from quadkit.web import throttle, RateLimitModule

    # Boot-time module config
    app.add_module(RateLimitModule.configure(
        backend="memory",            # "redis" | "memory"
        default_limit="100/minute",  # applied when no route-level @throttle
    ))

    class APIController(Controller):
        @get("/search")
        @throttle("30/minute")
        async def search(self, request: Request) -> list[dict]: ...

        @post("/upload")
        @throttle("5/hour", by="user")
        async def upload(self, request: Request) -> dict: ...

        @get("/public")
        @throttle("1000/hour", by="ip")
        async def public_data(self, request: Request) -> dict: ...
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.infra.redis import RedisClientProtocol

__all__ = ["RateLimitModule", "throttle"]

# ---------------------------------------------------------------------------
# Rate string parsing
# ---------------------------------------------------------------------------

_WINDOW_MAP: dict[str, int] = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}

_RATE_RE = re.compile(
    r"^(\d+)\s*/\s*(" + "|".join(_WINDOW_MAP) + r")$",
    re.IGNORECASE,
)


def _parse_rate(rate: str) -> tuple[int, int]:
    """Parse a rate string like ``"30/minute"`` into ``(max_requests, window_seconds)``.

    Args:
        rate: Rate string in the format ``"<count>/<unit>"`` where unit is
            one of ``second``, ``minute``, ``hour``, or ``day`` (plural forms
            are also accepted).

    Returns:
        Tuple of ``(max_requests, window_seconds)``.

    Raises:
        ValueError: If the rate string is not in the expected format.
    """
    m = _RATE_RE.match(rate.strip())
    if not m:
        raise ValueError(
            f"Invalid rate string {rate!r}. "
            "Expected format: '<count>/<unit>' where unit is "
            "second/minute/hour/day (e.g. '30/minute', '5/hour')."
        )
    max_requests = int(m.group(1))
    window_seconds = _WINDOW_MAP[m.group(2).lower()]
    return max_requests, window_seconds


# ---------------------------------------------------------------------------
# @throttle decorator
# ---------------------------------------------------------------------------


def throttle(
    rate: str,
    *,
    by: Literal["user", "ip", "endpoint"] = "user",
) -> Callable[[Any], Any]:
    """Rate-limit a route handler using a human-readable rate string.

    This is ergonomic sugar over the lower-level
    :func:`~quadkit.web.middleware.rate_limit.rate_limit` decorator.

    Args:
        rate: Rate string in ``"<count>/<unit>"`` format, e.g.
            ``"30/minute"``, ``"5/hour"``, ``"100/second"``.
        by: Scope for the rate limit key:

            * ``"user"`` — per authenticated user (falls back to IP when
              ``request.state.user`` is not set).
            * ``"ip"`` — per client IP address.
            * ``"endpoint"`` — per route path + HTTP method.

    Returns:
        Decorator that enforces the rate limit on the decorated handler.

    Raises:
        ValueError: If *rate* is not a valid rate string.

    Example::

        @get("/search")
        @throttle("30/minute")
        async def search(self, request: Request) -> list[dict]: ...

        @post("/upload")
        @throttle("5/hour", by="user")
        async def upload(self, request: Request) -> dict: ...
    """
    max_requests, window_seconds = _parse_rate(rate)

    from quadkit.web.middleware.rate_limit import rate_limit as _rate_limit

    return _rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        scope=by,
    )


# ---------------------------------------------------------------------------
# RateLimitModule
# ---------------------------------------------------------------------------


class RateLimitModule:
    """Module-level rate limiting configuration.

    Registers a :class:`~quadkit.web.di.rate_limit.RateLimitProvider` in
    the application's DI container so that route-level ``@throttle`` and
    ``@rate_limit`` decorators can resolve a limiter from the container.

    Usage::

        app.add_module(RateLimitModule.configure(
            backend="redis",
            default_limit="100/minute",
        ))

        # Development / testing — no external service required:
        app.add_module(RateLimitModule.configure(backend="memory"))
    """

    @classmethod
    def configure(
        cls,
        *,
        backend: Literal["redis", "memory"] = "memory",
        default_limit: str | None = None,
        redis_client: RedisClientProtocol | None = None,
        enabled: bool = True,
    ) -> Any:
        """Create a :class:`~quadkit.di.module.DynamicModule` that wires up
        rate limiting.

        Args:
            backend: Storage backend.  ``"redis"`` uses atomic Lua scripts
                (recommended for production); ``"memory``" uses a
                process-local sliding window (suitable for development and
                single-process deployments).
            default_limit: Optional default rate limit validated at module
                configuration time. Scope note: global (all-routes) enforcement
                lives in the ASGI ``RateLimitMiddleware``, configured through
                the ``[web.rate_limit]`` section of ``application.yaml`` —
                this kwarg does not wire that middleware; per-route limits are
                enforced by :func:`throttle` with the module-provided limiter.
            redis_client: Pre-built Redis client satisfying
                :class:`~quadkit.contracts.infra.redis.RedisClientProtocol`.
                Only used when ``backend="redis"``.  When *None*, the provider
                resolves one from the container at boot time.
            enabled: When ``False`` the rate limiter is not started.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.di.module import DynamicModule
        from quadkit.web.di.rate_limit import RateLimitProvider

        if default_limit is not None:
            # Validate at module-configuration time so errors surface early.
            _parse_rate(default_limit)

        rate_provider = RateLimitProvider(
            redis_client=redis_client if backend == "redis" else None,
            enabled=enabled,
            backend=backend,
        )

        # Build a minimal "wrapper" module class to satisfy DynamicModule
        from quadkit.di.module import module

        @module()
        class _RateLimitModuleClass:
            pass

        return DynamicModule(
            module=_RateLimitModuleClass,
            providers=[rate_provider],
            is_global=True,
        )
