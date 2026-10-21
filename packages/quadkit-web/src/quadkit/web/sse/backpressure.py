"""SSE improvements with backpressure and retry support.

Adds backpressure handling, Last-Event-ID resume, and connection events.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.web.transport.responses import StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


class SSEBackpressureHandler:
    """Handles backpressure for SSE streams."""

    def __init__(self, max_buffer_size: int = 100):
        self.max_buffer_size = max_buffer_size
        self._queue: asyncio.Queue | None = None
        self._closed = False

    @property
    def queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self.max_buffer_size)
        return self._queue

    async def send(self, event: str, data: str, event_id: str | None = None) -> bool:
        """Send an event. Returns False if buffer is full (backpressure)."""
        if self._closed:
            return False

        message = {"event": event, "data": data}
        if event_id:
            message["id"] = event_id

        try:
            self.queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            # Buffer full - apply backpressure
            return False

    async def wait_for_space(self, timeout: float = 5.0) -> bool:
        """Wait for space in the buffer."""
        try:
            await asyncio.wait_for(
                self.queue.join(),
                timeout=timeout,
            )
            return True
        except TimeoutError:
            return False

    def close(self) -> None:
        """Close the handler."""
        self._closed = True

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield events from the buffer."""
        while not self._closed:
            try:
                event = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0,
                )
                yield event
                self.queue.task_done()
            except TimeoutError:
                continue


class SSERetryTracker:
    """Tracks Last-Event-ID for resume support."""

    def __init__(self) -> None:
        self._last_event_id: str | None = None
        self._event_history: dict[str, dict[str, Any]] = {}
        self._max_history = 1000

    @property
    def last_event_id(self) -> str | None:
        return self._last_event_id

    def set_last_event_id(self, event_id: str) -> None:
        """Set the last event ID from request header."""
        self._last_event_id = event_id

    def record_event(self, event_id: str, event: str, data: str) -> None:
        """Record an event for potential resume."""
        self._last_event_id = event_id
        self._event_history[event_id] = {
            "event": event,
            "data": data,
            "id": event_id,
        }

        # Trim history if too large
        if len(self._event_history) > self._max_history:
            # Remove oldest
            oldest = next(iter(self._event_history))
            del self._event_history[oldest]

    def get_events_after(self, event_id: str) -> list[dict[str, Any]]:
        """Get events after a given event ID for resumption."""
        result = []
        found = False

        for eid, event in self._event_history.items():
            if eid == event_id:
                found = True
                continue
            if found:
                result.append(event)

        return result


class SSEConnectionEvents:
    """Callbacks for SSE connection lifecycle events."""

    def __init__(
        self,
        on_connect: Callable | None = None,
        on_disconnect: Callable | None = None,
        on_error: Callable | None = None,
    ):
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_error = on_error

    async def fire_connect(self, *args: Any, **kwargs: Any) -> None:
        if self.on_connect:
            if asyncio.iscoroutinefunction(self.on_connect):
                await self.on_connect(*args, **kwargs)
            else:
                self.on_connect(*args, **kwargs)

    async def fire_disconnect(self, *args: Any, **kwargs: Any) -> None:
        if self.on_disconnect:
            if asyncio.iscoroutinefunction(self.on_disconnect):
                await self.on_disconnect(*args, **kwargs)
            else:
                self.on_disconnect(*args, **kwargs)

    async def fire_error(self, error: Exception, *args: Any, **kwargs: Any) -> None:
        if self.on_error:
            if asyncio.iscoroutinefunction(self.on_error):
                await self.on_error(error, *args, **kwargs)
            else:
                self.on_error(error, *args, **kwargs)


class SSEResponse:
    """Enhanced SSE response with backpressure and retry support.

    Uses a :class:`~quadkit.web.sse.heartbeat.SSEHeartbeatScheduler` shared
    across all active connections with the same ``heartbeat_interval``, so
    only **one** background asyncio task is needed regardless of concurrency.
    """

    def __init__(
        self,
        generator: AsyncIterator[Any],
        *,
        backpressure: bool = True,
        max_buffer: int = 100,
        retry_timeout: int = 5000,
        heartbeat_interval: float = 30.0,
        events: SSEConnectionEvents | None = None,
    ):
        self.generator = generator
        self.backpressure = backpressure
        self.max_buffer = max_buffer
        self.retry_timeout = retry_timeout
        self.heartbeat_interval = heartbeat_interval
        self.events = events or SSEConnectionEvents()
        self._handler = SSEBackpressureHandler(max_buffer)
        self._retry_tracker = SSERetryTracker()

    async def stream(self) -> AsyncIterator[str]:
        """Stream SSE events with backpressure handling."""
        from quadkit.web.sse.heartbeat import get_heartbeat_scheduler

        await self.events.fire_connect()

        # Register with the shared heartbeat scheduler instead of creating
        # a per-connection asyncio task (fixes W8.2 unbounded-task issue).
        scheduler = get_heartbeat_scheduler(self.heartbeat_interval)
        await scheduler.register(self._handler)

        try:
            # Send retry timeout
            yield f"retry: {self.retry_timeout}\n\n"

            async for event in self.generator:
                # Format as SSE
                if isinstance(event, dict):
                    data = event.get("data", "")
                    event_type = event.get("event", "message")
                    event_id = event.get("id")
                else:
                    data = str(event)
                    event_type = "message"
                    event_id = None

                # Record for retry
                if event_id:
                    self._retry_tracker.record_event(event_id, event_type, data)

                # Send with backpressure
                success = True
                if self.backpressure:
                    success = await self._handler.send(event_type, data, event_id)

                if success:
                    output = f"event: {event_type}\n"
                    for line in data.split("\n"):
                        output += f"data: {line}\n"
                    if event_id:
                        output += f"id: {event_id}\n"
                    output += "\n"
                    yield output

        except Exception as e:  # noqa: BLE001 — event dispatch errors must not crash the SSE stream
            await self.events.fire_error(e)
            raise
        finally:
            await scheduler.unregister(self._handler)
            await self.events.fire_disconnect()
            self._handler.close()

    def to_response(self) -> StreamingResponse:
        """Convert to a Starlette StreamingResponse."""
        return StreamingResponse(
            self.stream(),
            media_type="text/event-stream",
        )
