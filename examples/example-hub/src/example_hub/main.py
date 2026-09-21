"""Convention followed: **Application boot** — ``main()`` wraps ``asyncio.run(serve())``; ``serve()`` boots the app and awaits ``run_server_async`` with ``finally: stop()``.

Entry point for the demo hub.

Run::

    PYTHONPATH=src uv run python -m example_hub

``create_app()`` builds the application.  This file boots it,
mounts the child demos via Fleet, and runs the web server.
Host/port are read automatically from ``application.yaml`` —
no manual config wiring needed.
"""

from __future__ import annotations

import asyncio
import sys

from example_hub.app import create_app
from quadkit.logging import get_logger

logger = get_logger(__name__)


async def serve() -> None:
    """Boot and serve until interrupted.

    ``app.start()`` triggers the full lifecycle:
    register → freeze → boot (Fleet mounts children here) → server start.
    The ``finally`` block ensures ``stop()`` runs even on errors.
    """
    from example_hub.fleet import Fleet
    from quadkit.web.di.provider import WebProvider
    from quadkit.web.server.runner import run_server_async

    app = create_app()
    await app.start()
    try:
        # Resolve the WebProvider to get the underlying Starlette app.
        web = await app.container.resolve(WebProvider)
        if web.starlette is None:
            raise RuntimeError("hub starlette app missing")

        # Mount every child demo under /examples/<slug>/.
        fleet = await app.container.resolve(Fleet)
        await fleet.mount_all(web.starlette)

        # run_server_async reads host/port from application.yaml by default;
        # pass explicit kwargs to override (e.g. during tests).  It must be
        # awaited: serve() already runs inside an event loop, and the sync
        # run_server() refuses to block a running loop.
        await run_server_async(app)

        # server returned — release embedded children
        await fleet.aclose()
    finally:
        await app.stop()


def main() -> int:
    """Sync entry point: translate asyncio interrupts into exit codes.

    Convention: ``python -m <package>`` calls ``main()``.  Return 0 for
    success, 130 for keyboard interrupt — the shell will see this as the
    process exit code.
    """
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
