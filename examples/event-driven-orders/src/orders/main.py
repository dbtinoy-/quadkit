"""Convention followed: **Application boot** — ``main()`` wraps ``asyncio.run(serve())``; ``serve()`` boots the app and awaits ``run_server_async`` with ``finally: stop()``.

Standalone server entry point for the event-driven orders demo.

Run::

    cd examples/event-driven-orders
    PYTHONPATH=src uv run python -m orders

Host/port come from ``application.yaml`` — no hardcoded values.
The order lifecycle walkthrough is available from the browser console.

Lifecycle teaching notes:
- ``Application.start()`` boots every provider in dependency order,
  freezes the container, and yields a fully-wired application.
- Resolving ``WebProvider`` after start demonstrates post-start
  resolution; its auto-injected ``.config`` carries the server host/port.
- The ``OrdersProvider.boot()`` resolves ``OrdersApi``, which triggers
  handler and event-subscription wiring exactly once (singleton factory).
"""

from __future__ import annotations

import asyncio

from orders.app import create_app


async def serve() -> None:
    """Boot once and serve until interrupted; stop cleanly afterwards."""
    from quadkit.web.server.runner import run_server_async

    app = create_app()
    await app.start()
    try:
        await run_server_async(app)
    finally:
        await app.stop()


def main() -> int:
    """Start the standalone order console server."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
