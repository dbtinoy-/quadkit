# Production deployment

A Quadkit web service is one process serving one ASGI application.
Production readiness is configuration, not code changes: the knobs live
in `application.yaml`, and the environment is the override channel.

## Serve it

Two entry points cover the running styles:

```python
from quadkit.web.server import run_server, run_server_async

run_server(app)  # synchronous, blocks — use from __main__


async def serve_from_loop() -> None:
    await run_server_async(app)  # for code already inside a running loop
```

The `quadkit` CLI provides the third form, with the auto-detection a
single-process deploy wants:

```bash
# target is module:attribute; auto-detected when omitted
quadkit run my_app.app:create_app --host 0.0.0.0 --port 8000 \
    --workers 4 --no-reload --server granian
```

`run_server` raises `RuntimeError` if called inside a running event loop
— switch to `run_server_async` (or `quadkit run`) instead. See the
[async model](../concepts/async-model.md).

## Server configuration

The whole serving surface is `web.server` in `application.yaml`:

```yaml
web:
  server:
    host: 0.0.0.0
    port: 8000
    backend: granian   # which ASGI server to hand the app to
    workers: 4         # worker processes — the production lever
    reload: false      # hot reload; a development aid
    debug: false
```

- **backend** — `granian`, `uvicorn`, or `hypercorn`, matching the
  installed extra (`quadkit-web[granian]` — also what `quadkit[web]`
  pulls — `quadkit-web[uvicorn]`, `quadkit-web[hypercorn]`). Without a
  pinned backend the resolver prefers Granian, then Uvicorn.
- **workers** — process count for the selected backend. Put real
  capacity here rather than running `reload`, which is a development
  aid (`quadkit run` defaults to `--reload`, so pass `--no-reload` or
  set it in YAML for production).

Every key overrides from the environment with the `QK_` convention —
`QK_WEB__SERVER__WORKERS=8`, `QK_WEB__SERVER__PORT=8080` — which is how
a container image stays generic while replicas and ports come from the
orchestrator. See [configuration](../getting-started/configuration.md).

## Health and readiness

`/health` is the built-in probe. It reports the readiness of every
component you registered, and it distinguishes two things most probes
conflate: a component that is **absent** (`unknown` with the reason —
`"No database provider is registered"`) and one that is **failing**
(`unhealthy` with the error). Only the second decides the status code, so
a service that legitimately has no database answers `200` instead of
reporting itself as an outage — while a registered, unreachable database
still answers `503`. Register providers as you add backing services and
keep their `health_check()` truthful, and the probe turns `503` for the
reasons worth paging on.

Wire the orchestrator's readiness probe to `/health`; a plain TCP check
cannot tell you the difference between "port bound" and "dependencies
up", and `/health` exists precisely for that distinction.

## Security surface, by configuration

The defaults are conservative; the knobs are under `web.security`:

- **CSRF** — enabled by default (`enable_csrf: true`); cookie-based,
  with the token in the `csrf_token` cookie and the `X-CSRF-Token`
  header by default. API-only services disable it explicitly
  (`enable_csrf: false`) — and should say so in the file, like the
  shipped guide examples do.
- **Allowed hosts / CORS / security headers** — `allowed_hosts`, CORS
  settings, and `custom_headers` live under the same section; the
  generated OpenAPI and debug endpoints keep their own switches
  (`web.debug_routes`, `web.debug_routes_token`, gated by an
  environment flag) — none of which serve content you didn't opt into.

The full hardening checklist is in
[secure configuration](../security/secure-configuration.md).

## Before you deploy: the checklist

1. **Pin the 0.x line** — `quadkit-web==0.0.44` (or `>=0.0.44,<0.1.0`);
   minor releases can move APIs until 1.0. See
   [stability](../reference/stability.md).
2. **Serve with workers, not reload** — `web.server.workers` for
   capacity, `reload: false` in production.
3. **Check readiness, not ports** — point the readiness probe at
   `/health` and make failing components meaningful.
4. **Push secrets through the environment** — `QK_*` overrides; nothing
   secret in YAML.
5. **Run the tests that deploy with you** — the
   [test harness](../getting-started/testing.md) boots the real
   application; a green suite is a config regression check for free.
