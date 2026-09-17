"""Convention followed: **Application boot** — ``main()`` wraps
``asyncio.run(serve())``; ``serve()`` boots the app and awaits
``run_server_async`` with ``finally: stop()``.

Standalone server entry point for the Multi-Tenant Notes demo.
"""

from __future__ import annotations

import asyncio

from multi_tenant_notes.app import create_app


async def serve() -> None:
    """Start the Multi-Tenant Notes server and block until shutdown."""
    from quadkit.web.server.runner import run_server_async

    app = create_app()
    await app.start()
    try:
        await run_server_async(app)
    finally:
        await app.stop()


def main() -> int:
    """Entry point that runs the async server with graceful Ctrl-C handling."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "serve"]
