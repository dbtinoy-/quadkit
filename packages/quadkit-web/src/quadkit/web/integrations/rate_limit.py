"""Rate limiting integration for WebProvider."""

from __future__ import annotations

from typing import Any, cast

from starlette.applications import Starlette

from quadkit.contracts.exceptions import RateLimitError
from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.di.container import Container
from quadkit.logging import get_logger
from quadkit.web.middleware.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
)

logger = get_logger(__name__)


class RateLimitIntegration:
    """Handles rate limit middleware and handler configuration."""

    @staticmethod
    async def configure(app: Starlette, container: Container, web_config: Any) -> None:
        """Configure rate limit middleware and handlers."""
        if (
            not getattr(web_config, "rate_limit", None)
            or not web_config.rate_limit.enabled
        ):
            return

        rate_limiter = await container.resolve_optional(
            cast("Any", WebRateLimiterProtocol)
        )
        redis_client = None
        if rate_limiter is None:
            # Storage honesty: "memory" (or failed redis) constructs
            # RateLimiter() which logs the explicit multi-worker warning
            # (middleware/rate_limit.py) and then enforces in-memory.
            if getattr(web_config.rate_limit, "storage_backend", "memory") == "redis":
                # Imported here, not at module scope: `quadkit.web.di` binds
                # this integration in `di/provider.py`, so a module-level
                # import would close a cycle and make every module of
                # `quadkit.web.integrations` unimportable on its own. The
                # lookup itself is a container read the caller already holds.
                from quadkit.web.di.rate_limit import resolve_redis_client

                redis_client = await resolve_redis_client(container)
            rate_limiter = RateLimiter(redis_client)

        if rate_limiter:
            app.add_exception_handler(
                RateLimitError,
                RateLimitIntegration._rate_limit_handler,
            )
            app.add_middleware(
                RateLimitMiddleware,
                rate_limiter=cast("Any", rate_limiter),
                config=cast("Any", web_config.rate_limit),
            )
            logger.info("Rate limiting middleware configured")

    @staticmethod
    async def _rate_limit_handler(_request: Any, exc: Exception) -> Any:
        """Standard rate limit exceeded handler."""
        from quadkit.web.middleware.rate_limit import _rate_limit_429_response

        return _rate_limit_429_response(exc)
