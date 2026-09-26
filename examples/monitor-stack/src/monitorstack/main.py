"""Serve the monitor-stack REST API.

Convention followed: **Application boot** — ``create_app()`` builds the
composition root, this file boots it and runs the web server.  Host/port
are read automatically from ``application.yaml`` — no manual config wiring
needed.

Run::

    uv run python -m monitorstack

The server exposes:

- ``GET /api/monitor/health``           — run health checks
- ``GET /api/monitor/health/self``      — self health check
- ``GET /api/monitor/metrics``          — get all metrics
- ``POST /api/monitor/metrics/increment`` — increment a counter
- ``POST /api/monitor/metrics/gauge``   — set a gauge
- ``GET /api/monitor/traces``           — get trace spans
- ``POST /api/monitor/trace``           — create a trace span
"""

from __future__ import annotations

import asyncio
import sys

from monitorstack.app import create_app
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


__all__ = ["main", "serve"]
