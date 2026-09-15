"""Debug routes integration for WebProvider."""

from __future__ import annotations

from typing import Any

from starlette.applications import Starlette

from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.di.container import Container
from quadkit.logging import get_logger

logger = get_logger(__name__)


class DebugIntegration:
    """Handles debug routes and required client configuration."""

    @staticmethod
    async def configure(_app: Starlette, container: Container, provider: Any) -> None:
        """Initialize debug routes and required clients."""
        from quadkit.di.exceptions import UnresolvableDependencyError

        try:
            provider._debug_redis_client = await container.resolve(CacheBackendProtocol)
        except (
            AttributeError,
            TypeError,
            ImportError,
            RuntimeError,
            UnresolvableDependencyError,
        ) as e:
            logger.debug("Failed to resolve debug cache backend: %s", e)

        logger.info("Debug routes enabled at /debug/*")
