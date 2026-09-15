"""Rate-limit provider for the Quadkit web integration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.web.middleware.rate_limit import RateLimiter

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class RateLimitProvider(Provider):
    """Standalone provider for rate-limiting services.

    Registers a :class:`~quadkit.web.middleware.rate_limit.RateLimiter` in the
    DI container and lazily resolves a Redis client from the container at boot
    time when none is supplied at construction.
    """

    name = "rate_limit"

    def __init__(
        self,
        redis_client: Any = None,
        enabled: bool = True,
    ) -> None:
        """Initialize rate limit provider.

        Args:
            redis_client: Optional pre-built Redis client for rate limiting.
            enabled: When ``False`` the provider skips all registration/boot.
        """
        super().__init__(name=self.name, priority=ProviderPriority.INFRASTRUCTURE)
        self.redis_client = redis_client
        self.enabled = enabled
        self.limiter: RateLimiter | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register rate limiter in the DI container.

        Args:
            container: DI container registrar.
        """
        if not self.enabled:
            logger.info("Rate limiting is disabled")
            return

        container.singleton(WebRateLimiterProtocol, factory=lambda: self.limiter)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Start the rate limit provider, resolving Redis from the container if needed."""
        if not self.enabled:
            return

        if self.redis_client is None:
            try:
                self.redis_client = await cast("Any", container).resolve("redis_client")
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Redis client not found in container (%s), rate limiting may be restricted",
                    e,
                )

        self.limiter = RateLimiter(self.redis_client)
        logger.info("RateLimitProvider started")

    async def shutdown(self) -> None:
        """Shutdown the rate limit provider."""
        self.limiter = None
        logger.info("RateLimitProvider stopped")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check rate-limit provider health.

        Returns:
            HealthCheckResult reflecting whether the limiter is initialised.
        """
        if not self.enabled:
            return HealthCheckResult(
                component="rate_limit",
                status=HealthStatus.HEALTHY,
                details={"enabled": False},
            )

        return HealthCheckResult(
            component="rate_limit",
            status=HealthStatus.HEALTHY if self.limiter else HealthStatus.UNHEALTHY,
            details={
                "enabled": True,
                "limiter_initialized": self.limiter is not None,
                "has_redis_client": self.redis_client is not None,
            },
        )


__all__ = ["RateLimitProvider"]
