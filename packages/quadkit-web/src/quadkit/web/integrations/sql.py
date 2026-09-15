"""SQL integration — attaches DB pool to ASGI app state for lifespan cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = get_logger(__name__)


class SQLIntegration:
    """Resolves the primary DB pool from the container and attaches it to app.state.

    Optional integration: silently skips if no SQL module is registered. This
    preserves the framework contract that web can run without a database.
    """

    @staticmethod
    async def configure(
        app: Starlette,
        container: ContainerResolverProtocol,
    ) -> None:
        """Attach the primary database pool to app.state.db_pool.

        Args:
            app: The ASGI application.
            container: The DI container resolver.

        Raises:
            LookupError: If no SQL module is registered (silent skip).
        """
        try:
            db_provider = await container.resolve(DatabaseProviderProtocol)
        except (LookupError, UnresolvableDependencyError, ModuleVisibilityError):
            logger.debug("No SQL module registered; SQLIntegration skipped")
            return

        if db_provider is None:
            logger.debug("No SQL module registered; SQLIntegration skipped")
            return

        pool = await db_provider.get_primary_pool()
        app.state.db_pool = pool
        logger.info("SQLIntegration: db_pool attached to app.state")
