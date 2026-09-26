"""Convention followed: **Application boot** — ``main()`` wraps ``asyncio.run(serve())``; ``serve()`` boots the app and awaits ``run_server_async`` with ``finally: stop()``.

Serve the auth web demo.

Run::

    uv run python -m auth_web            # serves application.yaml (:8081)

Host/port come from ``application.yaml`` (``web.server``); override without
editing the file via ``QK_WEB__SERVER__PORT``.
"""

from __future__ import annotations

import asyncio
import sys

from auth_web.app import create_app
from quadkit.logging import get_logger

logger = get_logger(__name__)


async def serve() -> None:
    """Boot and serve until interrupted.

    ``app.start()`` triggers the full lifecycle:
    register → freeze → boot (seeding happens here) → server start.
    The ``finally`` block ensures ``stop()`` runs even on errors.
    """
    from quadkit.web.server.runner import run_server_async

    app = create_app()
    await app.start()
    try:
        # run_server_async reads host/port from application.yaml by default;
        # pass explicit kwargs to override (e.g. during tests).
        await run_server_async(app)
    finally:
        await app.stop()


def main() -> int:
    """Sync entry point: translate asyncio interrupts into exit codes."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
