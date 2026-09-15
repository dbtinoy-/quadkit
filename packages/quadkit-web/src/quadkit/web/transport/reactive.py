"""SSE responses driven by quadkit.reactive EventStream sources."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from typing import Any

from quadkit.reactive import EventStream
from quadkit.web.transport.sse import EventSourceResponse, ServerSentEvent


def sse_from_stream(
    stream: EventStream[Any],
    serializer: Callable[[Any], str] | None = None,
    event_name: str | None = None,
    keepalive: float | None = 15.0,
) -> EventSourceResponse:
    """Expose a reactive stream as an EventSource-compatible SSE response.

    Args:
        stream: Any reactive stream.
        serializer: Optional item → frame-string serializer.
            Defaults to ``str(item)``.
        event_name: Optional SSE ``event:`` field value.
        keepalive: Emit ``: keepalive`` comments after this many seconds
            of silence; ``None`` disables.

    Returns:
        A Starlette StreamingResponse with ``text/event-stream``.

    Example:
        ```python
        @app.get("/dashboard/events")
        async def dashboard_events() -> EventSourceResponse:
            return sse_from_stream(
                orders.pipe(ops.filter(lambda e: e.type == "Order")),
                serializer=order_serializer,
            )
        ```
    """

    async def _items() -> AsyncGenerator[ServerSentEvent, None]:
        queue: asyncio.Queue[ServerSentEvent] = asyncio.Queue()
        done = asyncio.Event()
        background_tasks: set[asyncio.Task[Any]] = set()

        async def _drain() -> None:
            try:
                async for item in stream:
                    frame = serializer(item) if serializer else str(item)
                    await queue.put(ServerSentEvent(data=frame, event=event_name))
            finally:
                done.set()

        drain_task = asyncio.create_task(_drain())
        background_tasks.add(drain_task)
        drain_task.add_done_callback(background_tasks.discard)

        try:
            while not done.is_set():
                try:
                    if keepalive is None:
                        event = await queue.get()
                    else:
                        event = await asyncio.wait_for(queue.get(), timeout=keepalive)
                except TimeoutError:
                    yield ServerSentEvent(comment="keepalive")
                    continue
                yield event
            while not queue.empty():
                yield queue.get_nowait()
        finally:
            drain_task.cancel()
            with suppress(asyncio.CancelledError):
                await drain_task

    return EventSourceResponse(_items())
