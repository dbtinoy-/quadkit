"""Application lifecycle helpers.

Provides top-level async functions for starting, stopping, and running a
Quadkit :class:`Application` with OS signal handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.app.base import Application


async def run_application(app: Application) -> None:
    """Run an application with signal handling.

    Starts the application, waits for SIGINT/SIGTERM, then performs a
    graceful shutdown.  Handles :exc:`KeyboardInterrupt` and
    :exc:`SystemExit` silently so the process terminates cleanly.

    Args:
        app: The :class:`Application` instance to run.
    """
    try:
        await start_application(app)
        import asyncio
        import signal

        stop_event = asyncio.Event()
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await stop_application(app)


async def start_application(app: Application) -> None:
    """Start an application and its providers.

    Args:
        app: The :class:`Application` instance to start.
    """
    await app.start()


async def stop_application(app: Application) -> None:
    """Stop an application and its providers.

    Args:
        app: The :class:`Application` instance to stop.
    """
    await app.stop()


__all__ = ["run_application", "start_application", "stop_application"]
