# Your first app

Five minutes, one file, one endpoint. The same example runs as a real
test in CI — the file below is `docs/getting-started/examples/first_app.py`
in this repository, kept byte-identical with this page.

## 1. Create the app

<!-- snippet: examples/first_app.py -->
```python
"""Runnable companion to docs/getting-started/first-app.md.

A minimal Quadkit web application: one controller, one route, booted by
the web module. Run it directly to serve over HTTP::

    python first_app.py

then browse http://localhost:8000/hello?name=quadkit — plus /health,
/docs (Swagger UI) and /redoc, which the web module adds for you.
"""

from quadkit import Application
from quadkit.web import Controller, WebModule, get
from quadkit.web.server import run_server


class HelloController(Controller):
    """A controller maps HTTP routes to typed async methods."""

    @get("/hello")
    async def hello(self, name: str = "world") -> dict:
        """Query parameters bind to method arguments by name."""
        return {"message": f"hello, {name}"}


def create_app() -> Application:
    """Assemble the application; the web server boots it on start."""
    app = Application()
    app.add_modules([WebModule.configure(controllers=[HelloController])])
    return app


app = create_app()

if __name__ == "__main__":
    # Serves on 0.0.0.0:8000 by default; the backend resolves from
    # application.yaml's web.server.backend, preferring Granian, then
    # Uvicorn when they are installed.
    run_server(app, port=8000)
```

## 2. Run it

```bash
python first_app.py
```

## 3. Call it

```bash
curl "http://localhost:8000/hello?name=quadkit"
# {"message":"hello, quadkit"}
```

## 4. What you get for free

| Endpoint | What it is |
| --- | --- |
| `/hello` | Your route, with `name` bound from the query string |
| `/health` | Readiness probe aggregating every configured component |
| `/docs` | Swagger UI, generated from your controllers |
| `/redoc` | Redoc, same source |

`/docs`, `/redoc` and `/openapi.json` are served outside production; a
production deployment withholds them until it opts in with
`web.api_docs.enabled: true` — see
[secure configuration](../security/secure-configuration.md).

One honest note about `/health`: it reports the readiness of the
components you actually configured. On a bare web-only app nothing is
registered, so it answers `200` with `database` and `redis` marked
`unknown` and a reason beside each — `"No database provider is registered"`.
A component that is absent is not a component that is broken, and a probe
that cannot tell those apart restarts healthy services. Register a provider
and the same component becomes a real check: reachable answers `200`/`healthy`,
unreachable answers `503`/`unhealthy` with the error. Your own routes, like
`/hello`, are unaffected either way.

## What just happened

- `Application()` creates the app; `add_modules(...)` attaches the web
  feature. The application boots lazily — `create_app()` only assembles,
  no binding or startup happens until the server starts.
- `WebModule.configure(controllers=[...])` registers your controller.
  There is no router setup and no middleware boilerplate.
- `HelloController` is a plain typed class. Query parameters map to
  method arguments by name, so `?name=quadkit` becomes `name="quadkit"`.
- `run_server(app, port=8000)` serves the app. The backend resolves from
  `web.server.backend` in `application.yaml` when configured, otherwise
  it auto-prefers Granian, then Uvicorn, whichever is installed.
  `quadkit[web]` installs Granian.
- `run_server` is the synchronous entry point and **blocks the calling
  thread**; from a running event loop it raises `RuntimeError` — use
  `run_server_async` there instead (see [async model](../concepts/async-model.md)).

## Next steps

- [Configuration](./configuration.md) — give the app a name, pin the
  server backend, override everything from the environment.
- [Testing](./testing.md) — exercise these routes without starting a
  server at all.
