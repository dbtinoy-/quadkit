# quadkit-web reference

The async web layer: controllers, routing with signature-based binding,
middleware, OpenAPI generation, and pluggable ASGI server backends.
Runtime dependencies: Starlette, orjson, Jinja2, aiofiles — plus
`quadkit` and `quadkit-contracts`.

- **Install**: `pip install "quadkit-web[granian]"` · Python `>= 3.11`
- **Version** (lockstep with all thirteen distributions): `0.0.44`
  → [stability policy](./stability.md)
- **Issues**: <https://github.com/dbtinoy-/quadkit/issues>

## Extras

Verified against the package's `pyproject.toml`:

| Extra | Contents |
| --- | --- |
| `[granian]` / `[uvicorn]` / `[hypercorn]` | ASGI server backends |
| `[security]` | `itsdangerous` (signed tokens) |
| `[templates]` | Jinja2 template rendering |
| `[websocket]` | `websockets` — WebSocket support |
| `[client]` | `httpx` — HTTP client |
| `[test]` | test dependencies + `quadkit-testing` |
| `[docs]` / `[dev]` / `[all]` | tooling / everything |

> The distribution alone ships *no* server backend: install one backend
> extra, or use `quadkit[web]` which resolves to
> `quadkit-web[granian]`.

## Public entry points

```python
from quadkit.web import (
    Controller, WebModule,                # controllers + module
    get, post, put, patch, delete,        # route decorators
    body, query, path, header, cookie, form, file,  # parameter sources
    HTTPError, error_status,              # error signalling
    Result, Ok, Err,                      # re-exported from core
    JSONResponse, HTMLResponse, StreamingResponse, FileResponse,
    RedirectResponse, BackgroundTasks,
)
from quadkit.web.server import run_server, run_server_async
```

Guides: [web API](../guides/web-api.md) ·
[middleware](../guides/middleware.md) ·
[error handling](../guides/error-handling.md) ·
[production deployment](../guides/production-deployment.md).

## Configuration (`web.*`)

Typed sections validated at boot (all overridable via `QK_WEB__*`):

- `web.server` — `host`, `port`, `backend`, `workers`, `reload`, `debug`.
- `web.security` — `enable_csrf` (default **on**), `allowed_hosts`,
  CORS, `custom_headers`.
- `web.openapi_*` / `web.api_docs` — generated docs surface
  (`/docs`, `/redoc`, `/openapi.json`).
- `web.debug_routes` (+ `_token`, environment gate) — opt-in debug
  surface.

## Error handling

Errors render as RFC 7807 problem bodies: domain exceptions map by
status table, `HTTPError` gives direct control, body validation answers
`422` with per-field errors. See the
[error-handling guide](../guides/error-handling.md).

## Testing

[`quadkit-testing`](./quadkit-testing.md) provides `WebTestBed`, an
in-process client that boots your app via `Application` (or a
`WebProvider`) and asserts on responses without a listening socket.
