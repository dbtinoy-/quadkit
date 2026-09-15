"""Shared SSE heartbeat scheduler.

Instead of one asyncio task per SSE connection, a single ``SSEHeartbeatScheduler``
task fires heartbeats to all active connections.  This keeps the number of live
asyncio tasks proportional to the number of **distinct heartbeat intervals** used,
not the number of open connections.

Usage::

    from quadkit.web.sse.heartbeat import get_heartbeat_scheduler

    scheduler = get_heartbeat_scheduler(interval=30.0)
    await scheduler.start()            # once, at app startup (or lazily)

    token = scheduler.register(handler)
    # ... stream events ...
    scheduler.unregister(token)

The ``SSEResponse`` class integrates this automatically.
"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)

# Heartbeat payload — a comment line keeps the connection alive without
# triggering the client's `message` event listener.
_HEARTBEAT_PAYLOAD = ": heartbeat\n\n"


class SSEHeartbeatScheduler:
    """Single-task heartbeat scheduler for multiple SSE connections.

    Fires a heartbeat comment to all registered ``SSEBackpressureHandler``
    instances at the configured ``interval``.  Uses one background asyncio
    task regardless of how many connections are active.

    Args:
        interval: Seconds between heartbeat messages (default: 30.0).
        tick_resolution: How often (in seconds) the scheduler checks whether
            heartbeats are due.  Lower values give more accurate timing at
            the cost of slightly more CPU work (default: 1.0).
    """

    def __init__(
        self,
        interval: float = 30.0,
        tick_resolution: float = 1.0,
    ) -> None:
        self.interval = interval
        self.tick_resolution = tick_resolution
        # Use a plain set with lock rather than WeakSet so we can track
        # last-sent times without keeping the handler alive.
        self._handlers: set[Any] = set()
        self._last_sent: dict[int, float] = {}  # id(handler) → last send time
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background heartbeat loop (idempotent)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="sse-heartbeat-scheduler")

    async def stop(self) -> None:
        """Stop the background heartbeat loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def register(self, handler: Any) -> None:
        """Register an SSE connection handler for heartbeats.

        Args:
            handler: An ``SSEBackpressureHandler`` instance.
        """
        async with self._lock:
            self._handlers.add(handler)
            self._last_sent[id(handler)] = ambient_clock.monotonic()
        # Start lazily if not already running
        if not self._running:
            await self.start()

    async def unregister(self, handler: Any) -> None:
        """Unregister a handler when the connection closes.

        Args:
            handler: The previously registered handler.
        """
        async with self._lock:
            self._handlers.discard(handler)
            self._last_sent.pop(id(handler), None)

    async def _loop(self) -> None:
        """Main heartbeat loop — runs until stopped."""
        while self._running:
            await asyncio.sleep(self.tick_resolution)
            now = ambient_clock.monotonic()
            async with self._lock:
                handlers_snapshot = list(self._handlers)

            for handler in handlers_snapshot:
                hid = id(handler)
                last = self._last_sent.get(hid, now)
                if now - last >= self.interval:
                    try:
                        await handler.send("heartbeat", _HEARTBEAT_PAYLOAD)
                        async with self._lock:
                            self._last_sent[hid] = now
                    except Exception:  # noqa: BLE001 — one dead handler must not kill heartbeats for the rest
                        # Handler may already be closed; ignore silently.
                        pass

    @property
    def active_connections(self) -> int:
        """Number of SSE connections currently registered."""
        return len(self._handlers)


# Module-level cache: interval → scheduler
_schedulers: dict[float, SSEHeartbeatScheduler] = {}
_scheduler_lock: asyncio.Lock | None = None


def get_heartbeat_scheduler(
    interval: float = 30.0,
) -> SSEHeartbeatScheduler:
    """Return (creating if necessary) a shared scheduler for ``interval``.

    All SSE connections with the same heartbeat interval share one scheduler
    instance and therefore one background asyncio task.

    Args:
        interval: Heartbeat interval in seconds.

    Returns:
        The shared ``SSEHeartbeatScheduler`` for this interval.
    """
    key = interval
    if key not in _schedulers:
        _schedulers[key] = SSEHeartbeatScheduler(interval=interval)
    return _schedulers[key]


__all__ = ["SSEHeartbeatScheduler", "get_heartbeat_scheduler"]
