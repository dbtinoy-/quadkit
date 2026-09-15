"""ASGI lifespan and application setup helpers for the web provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import inspect
from typing import TYPE_CHECKING

from quadkit.logging import get_logger
from quadkit.web.hooks import WebServerStartedHook, WebServerStoppedHook

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = get_logger(__name__)


async def _emit_action(app: Starlette, hook_name: str, payload: object) -> None:
    """Emit a lifecycle action hook when the app is wired with a registry."""
    hooks = getattr(app.state, "hook_registry", None)
    if hooks is None:
        return

    await hooks.call_action(hook_name, payload=payload)


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """ASGI lifespan manager for the Starlette application.

    Handles startup diagnostics and graceful shutdown of shared resources
    attached to ``app.state`` (database pool, Redis client, etc.).
    """
    logger.info("Starting web application lifespan")

    # Initialize background_tasks if not already present
    if not hasattr(app.state, "background_tasks"):
        app.state.background_tasks = []

    # Diagnostics for tests that expect debug logs on missing resources
    if not hasattr(app.state, "db_pool"):
        logger.debug(
            "Database pool not found in app state, skipping cleanup registration",
        )

    await _emit_action(app, "server.started", WebServerStartedHook())

    yield

    logger.info("Shutting down web application lifespan")

    # 1. Cleanup DB Pool
    if hasattr(app.state, "db_pool"):
        try:
            pool = app.state.db_pool
            if hasattr(pool, "close"):
                res = pool.close()
                if hasattr(res, "__await__") or inspect.isawaitable(res):
                    await res
        except Exception:  # noqa: BLE001 — best-effort DB pool cleanup, must not crash shutdown
            logger.exception("Error closing DB pool")

    # 2. Cleanup Redis Client
    if hasattr(app.state, "redis_client"):
        try:
            client = app.state.redis_client
            if hasattr(client, "close"):
                res = client.close()
                if hasattr(res, "__await__") or inspect.isawaitable(res):
                    await res
        except Exception:  # noqa: BLE001 — best-effort Redis client cleanup, must not crash shutdown
            logger.exception("Error closing Redis client")

    await _emit_action(app, "server.stopped", WebServerStoppedHook())

    logger.debug("Web application lifespan ended")


__all__ = ["lifespan"]
