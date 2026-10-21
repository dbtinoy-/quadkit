"""Request body size limit middleware.

Rejects requests whose declared ``Content-Length`` exceeds a configurable
threshold before the body is read.  This prevents an attacker from posting a
gigabyte-sized payload that would exhaust application memory.

Usage::

    app.add_middleware(RequestBodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)

Or via ``WebConfig.max_body_size`` — ``WebProvider`` adds this middleware
automatically when ``max_body_size`` is set on the config.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from quadkit.logging import get_logger

logger = get_logger(__name__)

_10_MB = 10 * 1024 * 1024  # 10 MiB — used as default sentinel


class RequestBodySizeLimitMiddleware:
    """ASGI middleware that rejects oversized request bodies.

    Checks the ``Content-Length`` header on every incoming HTTP request.  If
    the declared size exceeds ``max_body_size`` a ``413 Request Entity Too
    Large`` response is returned immediately — the body is never read into
    memory.

    Note: Two enforcement paths: the declared ``Content-Length`` is checked
    before the body is read (fast 413); a body without a declared length
    (chunked transfer-encoding) is counted as it streams and is rejected
    with 413 once the accumulated bytes exceed ``max_body_size``.

    Args:
        app: The ASGI application to wrap.
        max_body_size: Maximum allowed body size in bytes.  Defaults to
            10 MiB (10 × 1024 × 1024 bytes).
    """

    def __init__(self, app: ASGIApp, max_body_size: int = _10_MB) -> None:
        """Initialise the middleware.

        Args:
            app: The inner ASGI application.
            max_body_size: Byte limit.  Requests with a ``Content-Length``
                header exceeding this value receive a 413 response.
        """
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the body size limit on HTTP requests.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.

        Note:
            Two enforcement paths: the declared ``Content-Length`` is checked
            before the body is read (fast 413); a body without a declared
            length (chunked transfer-encoding) is counted as it streams and
            is rejected with 413 once the accumulated bytes exceed
            ``max_body_size``.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers: dict[bytes, bytes] = {
            k.lower(): v for k, v in scope.get("headers", [])
        }
        content_length_bytes = headers.get(b"content-length")

        if content_length_bytes is not None:
            try:
                content_length = int(content_length_bytes)
            except ValueError:
                content_length = 0

            if content_length > self.max_body_size:
                logger.warning(
                    "request_body_too_large",
                    content_length=content_length,
                    max_body_size=self.max_body_size,
                    path=scope.get("path", ""),
                )
                response = _413_response()
                await response(scope, receive, send)
                return

        # Stream-count bodies without a declared length (chunked encoding).
        received_bytes = 0
        aborted = False

        async def counting_receive() -> Message:
            nonlocal received_bytes, aborted
            message = await receive()
            if message["type"] == "http.request" and not aborted:
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_size:
                    aborted = True
                    logger.warning(
                        "request_body_too_large_streamed",
                        received_bytes=received_bytes,
                        max_body_size=self.max_body_size,
                        path=scope.get("path", ""),
                    )
                    response = _413_response()
                    await response(scope, receive, send)
                    return {
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
            return message

        await self.app(scope, counting_receive, send)


def _413_response() -> ASGIApp:
    """Return a minimal 413 ASGI response callable."""

    async def respond(scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"connection", b"close"],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"detail":"Request Entity Too Large: body size exceeds limit"}',
                "more_body": False,
            }
        )

    return respond


__all__ = ["RequestBodySizeLimitMiddleware"]
