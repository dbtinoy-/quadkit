# quadkit-web

![Quadkit](https://raw.githubusercontent.com/dbtinoy-/quadkit/main/banner.jpg)

[![PyPI](https://img.shields.io/pypi/v/quadkit-web?color=%2322c55e&label=pypi)](https://pypi.org/project/quadkit-web/)
[![Python](https://img.shields.io/pypi/pyversions/quadkit-web?color=%2322c55e)](https://pypi.org/project/quadkit-web/)
[![License](https://img.shields.io/pypi/l/quadkit-web?color=%2322c55e)](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE)

The async web layer for Quadkit: controllers with signature-based
binding, a `Result`-to-HTTP bridge, middleware pipelines, and generated
OpenAPI docs — built on Starlette, server-backend agnostic.

For application developers building HTTP services: define controllers,
attach the web module, and serve on Granian, Uvicorn, or Hypercorn.

## The quadkit family

| Package | Role |
| --- | --- |
| [`quadkit-contracts`](https://pypi.org/project/quadkit-contracts/) | zero-dependency protocols, types, exception hierarchy |
| [`quadkit`](https://pypi.org/project/quadkit/) | the framework core — DI container, modules, config, logging, `Result` |
| [`quadkit-web`](https://pypi.org/project/quadkit-web/) | ASGI layer — controllers, routing, middleware, OpenAPI docs |
| [`quadkit-cli`](https://pypi.org/project/quadkit-cli/) | project scaffolding and code generators |
| [`quadkit-testing`](https://pypi.org/project/quadkit-testing/) | in-process test beds, fakes, fixtures |

## Installation

The distribution ships no server by itself — install one backend (or
use `quadkit[web]`, which resolves to `quadkit-web[granian]`):

```bash
uv add "quadkit-web[granian]"   # default backend, ASGI
uv add "quadkit-web[uvicorn]"   # alternative backend
uv add "quadkit-web[hypercorn]" # alternative backend
```

Requires **Python >= 3.11**.

## Minimal working example

```python
from quadkit import Application
from quadkit.web import Controller, WebModule, get
from quadkit.web.server import run_server


class HelloController(Controller):
    @get("/hello")
    async def hello(self, name: str = "world") -> dict:
        return {"message": f"hello, {name}"}


def create_app() -> Application:
    app = Application()
    app.add_modules([WebModule.configure(controllers=[HelloController])])
    return app


if __name__ == "__main__":
    run_server(create_app(), port=8000)
```

`/hello` is yours; `/docs`, `/redoc`, `/openapi.json`, and `/health`
come with it. Full walkthrough:
[your first app](https://dbtinoy-.github.io/quadkit/getting-started/first-app/), then the
[web API guide](https://dbtinoy-.github.io/quadkit/guides/web-api/).

## Binding, not parsing

Handler signatures *are* the validation: `query()`, `path()`, `header()`,
`cookie()`, `form()`, and `body()` bind and convert request data to typed
values — a `DomainModel`-annotated parameter validates the whole JSON
body, and a malformed request is a `422` with per-field errors before
your code runs:

```python
from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.web import Controller, body, get, post, query


@dataclass
class CreateOrder(DomainModel):
    sku: str
    qty: int = 1


class OrdersController(Controller):
    @get("/orders")
    async def list_orders(self, page: int = query(1)) -> dict:
        return {"page": page}  # query param, converted to int

    @post("/orders")
    async def create_order(self, order: CreateOrder = body()) -> dict:
        return {"sku": order.sku, "qty": order.qty}  # validated body
```

Controllers can also be discovered by package instead of listed —
`WebModule.configure(discover=["my_app.controllers"])`. One security
note: cookie-based CSRF is on by default, so JSON clients send the
`X-CSRF-Token` header (or you disable CSRF for token-authenticated
APIs: `web.security.enable_csrf: false`). More composition —
middleware, guards, per-route rate limits — in the
[web API guide](https://dbtinoy-.github.io/quadkit/guides/web-api/) and the
[feature tour](https://github.com/dbtinoy-/quadkit/blob/main/docs/guides/examples/features/README.md).

## Optional extras

| Extra | Contents |
| --- | --- |
| `[granian]` / `[uvicorn]` / `[hypercorn]` | ASGI server backends |
| `[security]` | `itsdangerous` — signed tokens |
| `[templates]` | Jinja2 template rendering |
| `[websocket]` | `websockets` — WebSocket support |
| `[client]` | HTTP client |
| `[test]` / `[docs]` / `[dev]` / `[all]` | tooling bundles |

## Public API entry points

```python
from quadkit.web import (
    Controller,
    WebModule,
    get,
    post,
    put,
    patch,
    delete,
    body,
    query,
    path,
    header,
    cookie,
    form,
    HTTPError,
    error_status,
    JSONResponse,
    HTMLResponse,
    StreamingResponse,
    FileResponse,
    RedirectResponse,
    BackgroundTasks,
)
from quadkit.web.config import WebConfig, ServerConfig, RateLimitConfig
from quadkit.web.middleware import MiddlewareRegistry
from quadkit.web.server import run_server, run_server_async
```

`WebModule.configure(controllers=..., middleware=...)` is the assembly
point; `WebModule.stub()` gives a no-op web module for unit tests.

## Configuration

Everything is typed, validated at boot, and env-overridable
(`QK_WEB__...`):

| YAML path | Default | What it controls |
| --- | --- | --- |
| `web.server.host` / `port` | `0.0.0.0` / `8000` | bind address |
| `web.server.backend` | `granian` | `granian`, `uvicorn`, or `hypercorn` |
| `web.server.workers` | `1` | worker processes (production lever) |
| `web.server.reload` | `false` | hot reload (development aid) |
| `web.security.enable_csrf` | `true` | cookie-based CSRF protection |
| `web.security.cors.allowed_origins` | `[]` (deny-by-default) | CORS allow-list |
| `web.rate_limit.enabled` | `false` | opt-in rate limiting |
| `web.api_docs.enabled` | unset → on outside production | `/docs`, `/redoc` + `/openapi.json` |
| `web.max_body_size` | 10 MiB | request body cap |

Env overrides mirror the YAML path, e.g. `QK_WEB__SERVER__PORT=8080`,
`QK_WEB__SECURITY__CORS__ALLOWED_ORIGINS='["https://app.example.com"]'`.
See [configuration](https://dbtinoy-.github.io/quadkit/getting-started/configuration/).

## Error handling

Every failure renders as an RFC 7807 problem body: domain exceptions map
through a status table, `HTTPError` gives direct control, request-body
validation answers `422` with per-field errors.
[The error-handling guide](https://dbtinoy-.github.io/quadkit/guides/error-handling/) shows
all three paths with executable examples.

## Testing

`quadkit-testing`'s `WebTestBed` boots your app in-process and asserts
on responses — no listening socket, no mocking:

```python
async def test_hello() -> None:
    from quadkit.testing import WebTestBed

    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello", params={"name": "quadkit"})
        response.assert_status(200)
        assert response.json == {"message": "hello, quadkit"}
```

## Security

Conservative defaults: CSRF on, CORS deny-by-default, unexpected
exceptions contained to a minimal 500 body. Details and hardening:
[secure configuration](https://dbtinoy-.github.io/quadkit/security/secure-configuration/);
report vulnerabilities privately per [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md).

## Stability

Version `0.0.45` in the `0.x` series, released in lockstep with the
other four distributions; APIs may change between minor versions until
1.0 — pin an exact version (`quadkit-web==0.0.45`) or a tight range
(`>=0.0.45,<0.1.0`). Full policy:
[stability and compatibility](https://dbtinoy-.github.io/quadkit/reference/stability/).

## Links

- **Documentation** — <https://dbtinoy-.github.io/quadkit/>
- **Getting started** — <https://dbtinoy-.github.io/quadkit/getting-started/installation/>
- **Changelog** — <https://github.com/dbtinoy-/quadkit/blob/main/CHANGELOG.md>
- **Issues** — <https://github.com/dbtinoy-/quadkit/issues>
- **Security** — report privately per [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md)
- **Contributing** — [CONTRIBUTING.md](https://github.com/dbtinoy-/quadkit/blob/main/CONTRIBUTING.md)

Apache-2.0 — see [LICENSE](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE). "Quadkit" and the
Quadkit logo are trademarks of the project — see
[TRADEMARK.md](https://github.com/dbtinoy-/quadkit/blob/main/TRADEMARK.md).
