"""Convention followed: **Application boot** — ``main()`` wraps ``asyncio.run(serve())``; ``serve()`` boots the app and awaits ``run_server_async`` with ``finally: stop()``.

Standalone server entry point for the Events Timeline Lab."""

from __future__ import annotations

import asyncio

from timeline_lab.app import create_app


async def serve() -> None:
    from quadkit.web.server.runner import run_server_async

    application = create_app()
    await application.start()
    try:
        await run_server_async(application)
    finally:
        await application.stop()


def main() -> int:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


__all__ = ["main", "serve"]
