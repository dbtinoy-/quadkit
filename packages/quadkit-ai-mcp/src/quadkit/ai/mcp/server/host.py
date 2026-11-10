"""MCPServerHost — HTTP/SSE host for the MCP server.

Provides a raw ASGI application to host an MCPServer using
HTTP POST for messages and Server-Sent Events (SSE) for streaming.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.ai.mcp.transport.sse import SSETransport
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str, loads_str

if TYPE_CHECKING:
    from quadkit.ai.mcp.server.core import MCPServer

logger = get_logger(__name__)


class MCPServerHost:
    """ASGI application that hosts an MCP server.

    Creates an HTTP/SSE endpoint for an ``MCPServer``. Provides an ASGI
    ``__call__`` method which can be mounted by any ASGI host (for example
    Starlette) or run directly via Uvicorn.
    """

    def __init__(
        self,
        server: MCPServer,
        path: str = "/mcp",
    ) -> None:
        """Initialize the MCP server host.

        Args:
            server: The configured :class:`MCPServer` instance.
            path: Base path for the MCP endpoints (default: ``/mcp``).
        """
        self._server = server
        self._path = path.rstrip("/")
        self._transport = SSETransport(server=self)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """ASGI application entry point."""
        if scope["type"] != "http":
            return

        method = scope["method"]
        path = scope["path"]

        # 1. SSE Connection Endpoint: GET /mcp/sse
        if path == f"{self._path}/sse" and method == "GET":
            await self._handle_sse(scope, receive, send)
            return

        # 2. Message Endpoint: POST /mcp/messages
        if path == f"{self._path}/messages" and method == "POST":
            await self._handle_messages(scope, receive, send)
            return

        # 404 Not Found
        await self._send_response(send, 404, b"Not Found")

    async def _handle_sse(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """Handle Server-Sent Events connection."""
        await self._transport.start()

        headers = [
            (b"content-type", b"text/event-stream"),
            (b"cache-control", b"no-cache"),
            (b"connection", b"keep-alive"),
        ]

        # Add CORS headers if configured
        if getattr(self._server.config, "cors_origins", None):
            # For simplicity in this raw ASGI app, we just allow the origin or *
            headers.append((b"access-control-allow-origin", b"*"))

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": headers,
            }
        )

        # Send initial endpoint event
        # The client must send messages to the POST endpoint
        endpoint_url = f"{self._path}/messages"
        await self._send_sse_event(send, event="endpoint", data=endpoint_url)

        async def _stream_messages() -> None:
            try:
                while True:
                    await asyncio.sleep(0.1)  # small poll interval
                    messages = self._transport.get_queued_messages()
                    for msg in messages:
                        data = dumps_str(msg)
                        await self._send_sse_event(send, event="message", data=data)
            except asyncio.CancelledError:
                pass

        stream_task = asyncio.create_task(_stream_messages())

        try:
            while True:
                # Wait for client disconnect
                message = await receive()
                if message["type"] == "http.disconnect":
                    stream_task.cancel()
                    break
        finally:
            stream_task.cancel()
            await self._transport.stop()

    async def _handle_messages(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        """Handle incoming JSON-RPC messages via POST."""
        body = b""
        more_body = True

        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        try:
            payload = loads_str(body.decode("utf-8"))
        except ValueError:
            await self._send_response(send, 400, b"Invalid JSON")
            return

        # Process the message
        response = await self._server.handle_message(payload)

        # If there's a response, queue it via SSE transport
        if response is not None:
            await self._transport.send(response)

        # Always return 202 Accepted for POST messages in SSE transport
        await self._send_response(send, 202, b"Accepted")

    async def _send_sse_event(
        self,
        send: Any,
        event: str | None = None,
        data: str = "",
    ) -> None:
        """Format and send an SSE event."""
        payload = ""
        if event:
            payload += f"event: {event}\n"
        if data:
            # Handle multi-line data
            for line in data.splitlines():
                payload += f"data: {line}\n"
        payload += "\n"

        await send(
            {
                "type": "http.response.body",
                "body": payload.encode("utf-8"),
                "more_body": True,
            }
        )

    async def _send_response(
        self,
        send: Any,
        status: int,
        body: bytes,
        content_type: bytes = b"text/plain",
    ) -> None:
        """Send a standard HTTP response."""
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", content_type),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )


__all__ = ["MCPServerHost"]
