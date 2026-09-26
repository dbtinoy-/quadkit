"""Convention followed: **Application boot** — ``main()`` wraps ``asyncio.run(serve())``; ``serve()`` boots the app and awaits ``run_server_async`` with ``finally: stop()``.

Entry point for the api-keys demo.

Run::

    cd examples/auth-apikeys
    PYTHONPATH=src uv run python -m apikey_console

Host/port come from ``application.yaml`` — no hardcoded values.
"""
# Entry point is thin — just asyncio.run(serve()).
# Composition root handles all wiring; this file only manages the
# event loop lifecycle and shell-friendly exit codes.

from __future__ import annotations

import asyncio
import sys

from apikey_console.app import create_app
from quadkit.logging import get_logger

logger = get_logger(__name__)


async def serve() -> None:
    """Boot and serve until interrupted."""
    from quadkit.web.server.runner import run_server_async

    # Lazy import of the server runner. The web module's
    # run_server_async reads host/port from application.yaml by default.
    app = create_app()
    await app.start()
    try:
        # run_server_async reads host/port from application.yaml by default;
        # pass explicit kwargs to override (e.g. during tests).
        await run_server_async(app)
    finally:
        await app.stop()


def main() -> int:
    """Sync wrapper: translate interrupts into a shell-friendly exit code."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
