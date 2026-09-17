# Middleware

Middleware wraps the *whole* application — every request passes through
it, including the framework's own endpoints such as `/docs`. Compose it
for concerns that genuinely apply to everything: request logging,
metrics, tracing headers, tenant resolution.

The example below is `docs/guides/examples/middleware_app.py` in this
repository, kept byte-identical with this page and executed in CI.

## Writing middleware — the canonical pattern

There is one way to write middleware in Quadkit: a plain ASGI class. It
takes the next application in the chain in `__init__` and awaits it in
`__call__` — standard [ASGI](https://asgi.readthedocs.io/), nothing
framework-specific:

<!-- snippet: examples/middleware_app.py -->
```python
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
```

Three details make the example correct:

- **Register via the `middleware` parameter of `WebModule.configure`** —
  the value forwards to the web provider, which builds your middleware
  ahead of the built-in default stack. No global state, no side effects.
- **Check `scope["type"]`** — ASGI also carries `websocket` and
  `lifespan` scopes. Middleware that only understands HTTP must pass
  everything else through untouched, or websockets break.
- **Wrap `send` to modify responses** — headers live on the
  `http.response.start` message; mutate them there, then forward.

The companion test also asserts the header appears on `/docs`, the
framework-generated endpoint — proving the wrap covers the whole
application, not only your controllers.

## When *not* to reach for middleware

Anything scoped to a subset of routes — authentication, authorization,
input policies — belongs on the route, not in a global wrap. Quadkit
provides **guards** (e.g. `RoleGuard`, the `@roles(...)` decorator) and
**interceptors** (`WebInterceptorBase`, `@guard(...)`) for route-specific
concerns, and they are a better fit than conditional middleware.

## Next steps

- [Production deployment](./production-deployment.md) — the built-in
  security middleware (CORS, security headers, CSRF) and its config.
- [Error handling](./error-handling.md) — how failures inside and
  outside middleware surface as problem responses.
