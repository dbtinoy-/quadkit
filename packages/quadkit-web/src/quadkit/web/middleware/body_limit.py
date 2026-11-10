"""Request body size limit middleware.

Rejects a declared oversized ``Content-Length`` before invoking the app, and
aborts downstream reads when actual streamed bytes exceed the configured limit.
This is not a substitute for proxy/server limits or application transaction design.

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


class _BodyLimitExceeded(BaseException):
    """Internal request-abort signal, not an application input exception.

    It deliberately bypasses ordinary ``except Exception`` handlers: once a
    streamed body is truncated, downstream must not treat it as valid input.
    """


def _body_limit_group(exc: BaseException) -> bool:
    """Recognize the abort, including Starlette's task-group side effect.

    BaseHTTPMiddleware can report "No response returned" from ``call_next``
    alongside the real abort. Only that traceback-attributed companion is
    suppressible; arbitrary errors and cancellation must still propagate.
    """

    def leaves(error: BaseException) -> list[BaseException]:
        if isinstance(error, BaseExceptionGroup):
            return [leaf for child in error.exceptions for leaf in leaves(child)]
        return [error]

    def starlette_no_response(error: BaseException) -> bool:
        if not isinstance(error, RuntimeError) or str(error) != "No response returned.":
            return False
        trace = error.__traceback__
        while trace is not None:
            code = trace.tb_frame.f_code
            if code.co_name == "call_next" and code.co_filename.replace(
                "\\", "/"
            ).endswith("/starlette/middleware/base.py"):
                return True
            trace = trace.tb_next
        return False

    errors = leaves(exc)
    return any(isinstance(error, _BodyLimitExceeded) for error in errors) and all(
        isinstance(error, _BodyLimitExceeded) or starlette_no_response(error)
        for error in errors
    )


class RequestBodySizeLimitMiddleware:
    """ASGI middleware that rejects oversized request bodies.

    Checks the ``Content-Length`` header on every incoming HTTP request.  If
    the declared size exceeds ``max_body_size`` a ``413 Request Entity Too
    Large`` response is returned immediately — the body is never read into
    memory.

    The declared ``Content-Length`` is checked before the body is read. Actual
    bytes are also counted as the downstream application reads, including when
    the header is missing or inaccurate. An over-limit read aborts downstream
    processing; if a response has already started, it cannot be replaced.
    Apps that never read the body are not covered by the streaming check.

    Args:
        app: The ASGI application to wrap.
        max_body_size: Maximum allowed body size in bytes.  Defaults to
            10 MiB (10 × 1024 × 1024 bytes).
    """

    # Generated actions require an explicit declaration rather than silently
    # running against versions that fabricate an empty body after a 413.
    supports_streaming_body_abort_v1 = True

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
            Actual bytes are counted as downstream reads them. An oversized
            read aborts processing; an already-started response cannot be
            replaced, and unread request bodies cannot be measured here.
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

        # Always count actual bytes, including when Content-Length is absent,
        # invalid, or smaller than the body. Never fabricate an empty terminal
        # chunk: downstream might interpret it as a valid no-input request.
        received_bytes = 0
        exceeded = False
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received_bytes, exceeded
            if exceeded:
                raise _BodyLimitExceeded
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_size:
                    exceeded = True
                    logger.warning(
                        "request_body_too_large_streamed",
                        received_bytes=received_bytes,
                        max_body_size=self.max_body_size,
                        path=scope.get("path", ""),
                    )
                    raise _BodyLimitExceeded
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                raise _BodyLimitExceeded
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
            # A misbehaving inner app could catch BaseException and return.
            # Do not also let it turn the aborted read into a success response.
            if exceeded:
                raise _BodyLimitExceeded
        except BaseException as exc:
            if not _body_limit_group(exc) or response_started:
                # A response already on the wire cannot be replaced by a 413.
                # Preserve unrelated errors and cancellation, too.
                raise
            await _413_response()(scope, receive, send)


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
