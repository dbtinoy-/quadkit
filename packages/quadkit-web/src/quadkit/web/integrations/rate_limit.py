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
                try:
                    redis_client = await container.resolve("redis_client")
                except Exception as redis_err:  # noqa: BLE001 — degrade to memory
                    logger.warning(
                        "redis_client unresolvable; using in-memory: %r", redis_err
                    )
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
