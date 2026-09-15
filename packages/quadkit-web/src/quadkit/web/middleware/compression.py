"""Compression Middleware."""

from __future__ import annotations

import gzip
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.logging import get_logger

logger = get_logger(__name__)


class CompressionMiddleware:
    """Response compression middleware"""

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1024,
        compress_types: list[str] | None = None,
    ):
        self.app = app
        self.minimum_size = minimum_size
        self.compress_types = compress_types or [
            "text/*",
            "application/json",
            "application/javascript",
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process request and compress response if appropriate."""

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if client supports compression
        headers = dict(scope.get("headers", []))
        accept_encoding_bytes = headers.get(b"accept-encoding")
        accept_encoding = (
            accept_encoding_bytes.decode("latin-1") if accept_encoding_bytes else ""
        )
        client_supports_gzip = "gzip" in accept_encoding

        if not client_supports_gzip:
            await self.app(scope, receive, send)
            return

        # Track response for compression
        response_started = False
        response_status = 200
        response_headers = []
        response_body = b""
        content_type = ""

        async def send_compressed(message: Any) -> None:
            nonlocal \
                response_started, \
                response_status, \
                response_headers, \
                response_body, \
                content_type

            if message["type"] == "http.response.start":
                response_started = True
                response_status = message.get("status", 200)
                response_headers = list(message.get("headers", []))

                # Get content type
                for key, value in response_headers:
                    if key == b"content-type":
                        content_type = value.decode("latin-1")
                        break

            elif message["type"] == "http.response.body":
                if not response_started:
                    logger.warning(
                        "compression_body_before_start",
                        detail="http.response.body received before http.response.start — forwarding uncompressed",
                    )
                    await send(message)
                    return

                response_body += message.get("body", b"")

                # If this is the final message (no more body expected)
                if not message.get("more_body", False):
                    await self._compress_and_send(
                        send,
                        response_status,
                        response_headers,
                        response_body,
                        content_type,
                    )
                # Don't send yet if more body is coming
            else:
                await send(message)

        await self.app(scope, receive, send_compressed)

    async def _compress_and_send(
        self,
        send: Send,
        status: int,
        headers: list,
        body: bytes,
        content_type: str,
    ) -> None:
        """Compress response body and send."""

        # Check content type
        should_compress = any(
            pattern in content_type or pattern.replace("*", "") in content_type
            for pattern in self.compress_types
        )

        if not should_compress or len(body) < self.minimum_size:
            # Send uncompressed
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                },
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                },
            )
            return

        # Compress body
        compressed = gzip.compress(body)

        # Update headers
        headers = list(filter(lambda kv: kv[0] != b"content-length", headers))
        headers.append((b"content-encoding", b"gzip"))
        headers.append((b"content-length", str(len(compressed)).encode()))

        # Send compressed response
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            },
        )
        await send(
            {
                "type": "http.response.body",
                "body": compressed,
            },
        )
