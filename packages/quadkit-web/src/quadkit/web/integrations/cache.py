"""Cache integration — attaches Redis client to ASGI app state for lifespan cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = get_logger(__name__)


class CacheIntegration:
    """Resolves the cache backend and attaches Redis client to app.state.

    Optional integration: silently skips if no cache module is registered
    or if the backend doesn't expose an underlying Redis client (e.g., memory backend).
    """

    @staticmethod
    async def configure(
        app: Starlette,
        container: ContainerResolverProtocol,
    ) -> None:
        """Attach the Redis client to app.state.redis_client.

        Args:
            app: The ASGI application.
            container: The DI container resolver.

        Note:
            This integration only attaches the client for Redis backends.
            Memory backends don't have an underlying client and are skipped.
        """
        try:
            cache = await container.resolve(CacheBackendProtocol)
        except (LookupError, UnresolvableDependencyError, ValueError):
            logger.debug("No cache module registered; CacheIntegration skipped")
            return

        if cache is None:
            logger.debug("No cache module registered; CacheIntegration skipped")
            return

        if hasattr(cache, "get_underlying_client"):
            client = cache.get_underlying_client()
            if client is not None:
                app.state.redis_client = client
                logger.info("CacheIntegration: redis_client attached to app.state")
            else:
                logger.debug(
                    "Cache backend has no underlying client (memory backend?); "
                    "CacheIntegration skipped"
                )
        else:
            logger.debug(
                "Cache backend doesn't expose get_underlying_client; "
                "CacheIntegration skipped"
            )
