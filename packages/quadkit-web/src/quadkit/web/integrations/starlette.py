"""Creates and configures the Starlette ASGI application instance."""

from __future__ import annotations

from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware

from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


def build_starlette_app(
    middleware: list[Middleware],
    exception_handlers: dict[Any, Any],
    lifespan: Any,
    container: ContainerResolverProtocol,
) -> Starlette:
    """Construct and configure the Starlette ASGI application.

    Args:
        middleware: Pre-built middleware stack.
        exception_handlers: Exception handler mapping.
        lifespan: Lifespan context manager.
        container: Container resolver for state attachment.

    Returns:
        Configured Starlette application.
    """
    app = Starlette(
        middleware=middleware,
        lifespan=lifespan,
        exception_handlers=exception_handlers,
    )

    # Attach container to state and instance for access in middleware/handlers/tests
    app.state.container = container
    app.container = container  # type: ignore[attr-defined]

    logger.info("starlette_app_created", middleware_count=len(middleware))
    return app


__all__ = ["build_starlette_app"]
