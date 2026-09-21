"""Convention followed: **Application boot** — ``main()`` wraps
``asyncio.run(serve())``; ``serve()`` boots the app and awaits
``run_server_async`` with ``finally: stop()``.

Standalone server entry point for the storefront demo.

Run::

    cd examples/storefront
    PYTHONPATH=src uv run python -m storefront

Host/port come from ``application.yaml`` — no hardcoded values.
"""

from __future__ import annotations

import asyncio

from storefront.app import create_app


async def serve() -> None:
    """Boot and serve until interrupted.

    ``app.start()`` triggers the full lifecycle:
    register → freeze → boot (cross-module resolution happens here) →
    server start. The ``finally`` block ensures ``stop()`` runs even on
    errors.
    """
    from quadkit.web.server.runner import run_server_async

    app = create_app()
    await app.start()
    try:
        await run_server_async(app)
    finally:
        await app.stop()


def main() -> int:
    """Start the standalone storefront server."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "serve"]
