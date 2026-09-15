"""Request timing middleware."""

from __future__ import annotations

from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.primitives import clock as ambient_clock


class TimingMiddleware:
    """Pure ASGI middleware that adds request timing headers.

    10x faster than BaseHTTPMiddleware - no task creation overhead.
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Process-Time",
    ):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pure ASGI middleware implementation."""

        if scope["type"] != "http":
            # Pass through non-HTTP requests
            await self.app(scope, receive, send)
            return

        # Start timing
        start_time = ambient_clock.timestamp()

        # Wrap send to add timing header to response
        async def send_with_timing(message: Any) -> None:
            if message["type"] == "http.response.start":
                # Calculate duration and add header
                duration_ms = (ambient_clock.timestamp() - start_time) * 1000
                timing_header = f"{duration_ms:.2f}"

                headers = list(message.get("headers", []))
                # Add timing header
                headers.append([self.header_name.encode(), timing_header.encode()])
                message["headers"] = headers

            await send(message)

        # Process request
        await self.app(scope, receive, send_with_timing)
