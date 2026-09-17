"""Runnable companion to docs/guides/middleware.md.

A middleware is a plain ASGI class: it wraps the next application in the
chain in ``__init__`` and awaits it in ``__call__``. Registered via the
``middleware`` parameter of ``WebModule.configure`` — nothing else:

    pytest test_middleware_app.py
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from quadkit import Application
from quadkit.web import Controller, WebModule, get


class ServedByMiddleware:
    """Add an ``x-served-by`` header to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-served-by", b"quadkit"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_header)


class PingController(Controller):
    @get("/ping")
    async def ping(self) -> dict:
        return {"pong": True}


def create_app() -> Application:
    """User middleware runs ahead of the built-in default stack."""
    app = Application()
    app.add_modules([
        WebModule.configure(
            controllers=[PingController],
            middleware=[ServedByMiddleware],
        )
    ])
    return app


app = create_app()
