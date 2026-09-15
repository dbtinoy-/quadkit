# quadkit-web

Web layer for Quadkit Framework — ASGI, routing, middleware, and API tooling.

---

## Overview

`quadkit-web` provides an ASP.NET Core-inspired HTTP layer built on Starlette with constructor injection, a `Result`-to-HTTP bridge that maps domain errors to status codes automatically, first-class middleware, guard, and filter pipelines, and OpenAPI docs auto-generation.

---


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit quadkit-web[granian]

# With optional server backends
uv add "quadkit-web[uvicorn]"   # uvicorn
uv add "quadkit-web[hypercorn]"  # hypercorn
uv add "quadkit-web[security]"   # itsdangerous for signing
uv add "quadkit-web[templates]"  # Jinja2 template support
uv add "quadkit-web[websocket]"  # WebSocket support
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module
from quadkit.web import Controller, WebModule, WebProvider, get


class HelloController(Controller):
    @get("/hello")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello from Quadkit"}


@module(
    imports=[
        WebModule.configure(
            controllers=[HelloController],
            host="127.0.0.1",
            port=8000,
        )
    ]
)
class AppModule(Module):
    pass


async def main() -> None:
    async with Application.boot(modules=[AppModule]) as app:
        web = await app.container.resolve(WebProvider)
        web.run_server(host="127.0.0.1", port=8000)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

## Configuration

> **Zero-config usage:** Call `WebModule.configure()` with no arguments to use all defaults.

### Option 1 — YAML file

```yaml
# application.yaml
web:
  server:
    host: "0.0.0.0"
    port: 8000
    workers: 4
  cors:
    allowed_origins:
      - "https://app.example.com"
  rate_limit:
    enabled: true
    default_limit: "100/minute"
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_WEB__SERVER__HOST=0.0.0.0
export QK_WEB__SERVER__PORT=8080
export QK_WEB__SECURITY__CORS__ALLOWED_ORIGINS='["https://app.example.com"]'
```

### Option 3 — Python

```python
from quadkit.web import WebModule
from quadkit.web.config import WebConfig, ServerConfig, RateLimitConfig

WebModule.configure(
    controllers=[UserController, OrderController],
    web_config=WebConfig(
        server=ServerConfig(host="0.0.0.0", port=8080, workers=4),
        rate_limit=RateLimitConfig(
            enabled=True,
            default_limit=200,
            default_window=60,
        ),
    ),
)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `server.host` | `"0.0.0.0"` | `QK_WEB__SERVER__HOST` | Bind host |
| `server.port` | `8000` | `QK_WEB__SERVER__PORT` | Bind port |
| `server.workers` | `1` | `QK_WEB__SERVER__WORKERS` | Worker processes |
| `server.reload` | `False` | `QK_WEB__SERVER__RELOAD` | Auto-reload on code change |
| `cors.allowed_origins` | `["http://localhost:3000", "http://localhost:8001"]` | `QK_WEB__SECURITY__CORS__ALLOWED_ORIGINS` | CORS allow-list — wildcards blocked in production |
| `rate_limit.enabled` | `True` | `QK_WEB__RATE_LIMIT__ENABLED` | Enable rate limiting |
| `rate_limit.default_limit` | `100` | `QK_WEB__RATE_LIMIT__DEFAULT_LIMIT` | Requests per window |
| `rate_limit.default_window` | `60` | `QK_WEB__RATE_LIMIT__DEFAULT_WINDOW` | Window in seconds |
| `rate_limit.storage_backend` | `"memory"` | `QK_WEB__RATE_LIMIT__STORAGE_BACKEND` | `"memory"` or `"redis"` |
| `enable_auth` | `False` | `QK_WEB__ENABLE_AUTH` | Enable built-in auth middleware |
| `api_docs.enabled` | `True` | `QK_WEB__API_DOCS__ENABLED` | Enable `/docs` + `/redoc` |
| `max_body_size` | `10 MiB` | `QK_WEB__MAX_BODY_SIZE` | Request body size limit |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `WebModule.configure(controllers, discover, ...)` | Configure with controllers and server settings |
| `WebModule.stub()` | No-op module for unit testing |

## Key Features

- **Controller pattern** — subclass `Controller` and annotate methods with HTTP decorators
- **Result-to-HTTP bridge** — `Result[T, DomainError]` maps automatically to status codes (404, 422, 403, etc.)
- **HTTP decorators** — `@get`, `@post`, `@put`, `@delete`, `@patch`, `@websocket`, etc.
- **Auto-discovery** — `WebModule.configure(discover=["my_app.api.v1"])`
- **Middleware pipeline** — register ASGI middleware via `MiddlewareRegistry`
- **Exception filters** — `DefaultExceptionFilter` handles `DomainError` and `HTTPError` globally
- **Static files, API docs, debug routes** — configurable via `WebConfig`
- **Rate limiting** — per-path rules with memory or Redis storage backend
- **Security** — CORS wildcard blocked in production, CSRF enabled by default

## Testing

```python
from quadkit import Application
from quadkit.web import WebModule


async def test_controller():
    async with Application.boot(modules=[WebModule.stub()]) as app:
        web = await app.container.resolve(WebProvider)
        assert web.starlette is not None
```

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/web/module.py` | `WebModule.configure()` |
| `src/quadkit/web/di/provider.py` | `WebProvider` boot phases |
| `src/quadkit/web/routing/decorators.py` | HTTP decorators (`@get`, `@post`, etc.) |
| `src/quadkit/web/routing/result_bridge.py` | `ResultResponseMapper` for Result-to-HTTP mapping |
| `src/quadkit/web/config.py` | `WebConfig`, `ServerConfig`, `RateLimitConfig` |
| `src/quadkit/web/middleware/__init__.py` | ASGI middleware classes + `MiddlewareRegistry` |
| `src/quadkit/web/filters/__init__.py` | Exception filters |