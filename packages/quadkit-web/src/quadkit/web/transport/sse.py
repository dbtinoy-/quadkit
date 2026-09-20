"""Low-level Server-Sent Events transport.

For higher-level SSE with backpressure, retry, and handler patterns,
use ``quadkit_web.sse`` instead.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from starlette.responses import StreamingResponse

from quadkit.serialization import dumps


class ServerSentEvent:
    """Server-sent event"""

    def __init__(
        self,
        data: Any = None,
        event: str | None = None,
        event_id: str | None = None,
        retry: int | None = None,
        comment: str | None = None,
    ) -> None:
        self.data = data
        self.event = event
        self.event_id = event_id
        self.retry = retry
        self.comment = comment

    def encode(self) -> str:
        """Encode the event as SSE format"""
        # Build header lines conditionally
        lines = []
        if self.comment:
            lines.append(f": {self.comment}")
        if self.event:
            lines.append(f"event: {self.event}")
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        if self.retry:
            lines.append(f"retry: {self.retry}")

        # Handle data - split string by newlines or serialize object
        if self.data is None:
            data_lines = []
        elif isinstance(self.data, str):
            data_lines = self.data.split("\n")
        else:
            data_lines = [dumps(self.data).decode("utf-8")]

        # Append data lines (using list comprehension)
        lines.extend(f"data: {line}" for line in data_lines)
        lines.append("")  # Empty line to end the event
        return "\n".join(lines) + "\n"


class EventSourceResponse(StreamingResponse):
    """Server-sent events response"""

    def __init__(
        self,
        content: AsyncGenerator[ServerSentEvent, None],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        headers = headers or {}
        headers.update(
            {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

        async def event_generator() -> AsyncGenerator[str, None]:
            async for event in content:
                yield event.encode()

        super().__init__(
            content=event_generator(),
            status_code=status_code,
            headers=headers,
            media_type="text/event-stream",
        )


def sse_response(
    content: AsyncGenerator[ServerSentEvent, None],
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> EventSourceResponse:
    """Create a server-sent events response"""
    return EventSourceResponse(content, status_code, headers)
