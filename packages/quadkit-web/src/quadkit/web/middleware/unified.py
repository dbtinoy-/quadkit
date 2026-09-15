"""Unified middleware protocols and adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import ASGIApp, Receive, Scope, Send

# Re-export the canonical MiddlewareRegistry


class RequestResponseMiddlewareAdapter:
    """Adapter that wraps request/response middleware for ASGI.

    This allows legacy middleware that uses:
        process_request(request) -> None
        process_response(response) -> Response

    to work with the ASGI protocol.
    """

    def __init__(
        self,
        app: ASGIApp,
        process_request: Callable | None = None,
        process_response: Callable | None = None,
    ):
        self.app = app
        self.process_request = process_request
        self.process_response = process_response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope, receive)

        # Run request processing if available
        if self.process_request:
            await self.process_request(request)

        # Create a response wrapper to capture the response
        response_wrapper = {"status": None, "headers": None, "body": b""}

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                # Store status and headers
                response_wrapper["status"] = message["status"]
                response_wrapper["headers"] = message.get("headers", [])
                # Forward the start message to client
                await send(message)
            elif message["type"] == "http.response.body":
                # Store body and forward to client
                body = message.get("body", b"")
                response_wrapper["body"] += body
                await send(message)

        # Call the next middleware/app
        await self.app(scope, receive, send_wrapper)

        # Run response processing if available
        if self.process_response and response_wrapper.get("status") is not None:
            # Create a simple response-like object for the processor
            class SimpleResponse:
                def __init__(self, status: Any, headers: Any, body: Any) -> None:
                    self.status_code = status
                    self.headers = headers
                    self.body = body

            simple_response = SimpleResponse(
                response_wrapper["status"],
                response_wrapper["headers"],
                response_wrapper["body"],
            )
            processed = await self.process_response(simple_response)
            if processed:
                await processed(scope, receive, send)


class ASGIMiddlewareAdapter:
    """Adapter that provides ASGI interface for request/response middleware.

    Usage:
        # Old style:
        class MyMiddleware:
            async def process_request(self, request):
                ...

        # Wrap for ASGI:
        app = MyMiddleware(app)
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
