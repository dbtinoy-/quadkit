"""Rate-limit provider for the Quadkit web integration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.infra.redis import RedisClientProtocol
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

#: Container bindings consulted, in order, for the application's Redis client:
#: the typed registration first, then the named binding applications used
#: before :class:`~quadkit.contracts.infra.redis.RedisClientProtocol` existed.
_REDIS_LOOKUPS: tuple[object, ...] = (RedisClientProtocol, "redis_client")


async def resolve_redis_client(
    container: ContainerResolverProtocol,
) -> RedisClientProtocol | None:
    """Resolve the application's Redis client from the container.

    Args:
        container: Resolver the binding is read from.

    Returns:
        The bound client, or ``None`` when the container has none — callers
        then degrade to the process-local limiter.
    """
    for lookup in _REDIS_LOOKUPS:
        try:
            client = await container.resolve(lookup)
        except Exception as e:  # noqa: BLE001 — unbound keys of any shape raise
            logger.debug(
                "rate_limit_redis_client_miss",
                lookup=str(lookup),
                error=str(e),
            )
            continue
        if client is not None:
            return cast("RedisClientProtocol", client)
    return None


class RateLimitProvider(Provider):
    """Standalone provider for rate-limiting services.

    Registers a :class:`~quadkit.web.middleware.rate_limit.RateLimiter` in the
    DI container and lazily resolves a Redis client from the container at boot
    time when none is supplied at construction.

    A client reaches the container as a
    :class:`~quadkit.contracts.infra.redis.RedisClientProtocol` registration or
    as a named ``"redis_client"`` binding; see
    :func:`resolve_redis_client`.
    """

    name = "rate_limit"

    def __init__(
        self,
        redis_client: RedisClientProtocol | None = None,
        enabled: bool = True,
        backend: Literal["redis", "memory"] = "redis",
    ) -> None:
        """Initialize rate limit provider.

        Args:
            redis_client: Optional pre-built client satisfying
                :class:`~quadkit.contracts.infra.redis.RedisClientProtocol`.
            enabled: When ``False`` the provider skips all registration/boot.
            backend: ``"redis"`` uses the Redis-backed limiter (previous and
                default behaviour); ``"memory"`` binds the process-local
                sliding-window :class:`MemoryLimiter` and never touches Redis.
        """
        super().__init__(name=self.name, priority=ProviderPriority.INFRASTRUCTURE)
        self.redis_client: RedisClientProtocol | None = redis_client
        self.enabled = enabled
        self.backend = backend
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

        if self.backend == "memory":
            # RateLimiter with no Redis and no cache backend runs its
            # process-local sliding-window fallback branch — exactly the
            # "memory" mode the module docs promise, protocol-shaped
            # (check_rate_limit) for ambient @throttle resolution.
            self.limiter = RateLimiter(None)
            logger.info("RateLimitProvider started (memory backend)")
            return

        if self.redis_client is None:
            self.redis_client = await resolve_redis_client(container)
            if self.redis_client is None:
                logger.warning(
                    "rate_limit_redis_client_missing",
                    hint=(
                        'register RedisClientProtocol or a "redis_client" '
                        "binding, or use the memory backend"
                    ),
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


__all__ = ["RateLimitProvider", "resolve_redis_client"]
