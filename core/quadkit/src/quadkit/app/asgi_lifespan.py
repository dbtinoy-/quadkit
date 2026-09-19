"""ASGI lifespan protocol handling for :class:`~quadkit.app.base.Application`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.app.base import Application


async def handle_lifespan(
    app: Application,
    receive: Any,
    send: Any,
) -> None:
    """Handle ASGI lifespan protocol (startup/shutdown events).

    Extracted from ``Application._handle_lifespan`` to keep the base
    class under the 500-LOC budget; behavior is verbatim.
    """
    message = await receive()
    if message["type"] == "lifespan.startup":
        try:
            if app._state == app.state.__class__.CREATED:
                await app.start()
            await send({"type": "lifespan.startup.complete"})
        except BaseException:
            await send({"type": "lifespan.startup.failed"})
            raise
    message = await receive()
    if message["type"] == "lifespan.shutdown":
        try:
            await app.stop()
            await send({"type": "lifespan.shutdown.complete"})
        except BaseException:
            await send({"type": "lifespan.shutdown.failed"})
            raise
