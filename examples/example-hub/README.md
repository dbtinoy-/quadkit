# Demo Hub

> Module name: `example_hub` — run with `PYTHONPATH=src uv run python -m example_hub`

One port for the whole fleet. The hub boots every web demo's real Quadkit
`Application` **in-process** and mounts it under `/examples/<slug>/`, then serves
a status console that links to all of them.

No other ports are needed in embedded mode — and every demo still runs
standalone on its documented port (nothing about the demos was changed).

## Quadkit concepts used

| Concept | Where in this demo | Your app |
|---------|-------------------|----------|
| Composition root | `app.py` | Replace controllers/providers list |
| Provider lifecycle | `di/provider.py` | register() binds, boot() initializes |
| Fleet mounting | `fleet.py` | Mount child apps under /examples/ |
| Subsite rewriting | `subsite.py` | Rewrite HTML/JS for nested mounts |
| Web module | `app.py` → `WebModule.configure()` | Add your controllers |
| Status API | `controllers/api.py` | Expose health/status endpoints |

## What it shows

| Piece | Where | Quadkit API used |
|-------|-------|-------------------|
| Hub composition | `app.py` | `build_modules()`, `build_providers()`, `create_app()` |
| Child mounting | `fleet.py` | `Fleet.mount_all()` → `SubsiteMiddleware` |
| HTML/JS rewriting | `subsite.py` | `rewrite_html()`, `rewrite_js()` |
| Service registry | `services/registry.py` | `ServiceRegistry.web_services()` |
| Status endpoint | `controllers/api.py` | `@get("/api/status")` → `JSONResponse` |

## Run it

```bash
cd examples/example-hub
PYTHONPATH=src uv run python -m example_hub
```

Or from the repository root:

```bash
make demos-up        # start the hub (:7000), wait, then list demo states
make demos-status    # re-probe any time
make demos-down      # stop everything
```

Then open <http://127.0.0.1:7000>:

| URL | What |
|-----|------|
| `/` | Hub console — card per demo, green/red status, All/Capability/Auth filters |
| `/api/status` | JSON status for every embedded demo (`up` / `down`) |
| `/examples/resilient-rates/` | Each demo lives at `/examples/<slug>/` |

## Layout — read it in this order

| # | File | Lesson |
|---|------|--------|
| 1 | `src/example_hub/app.py` | ⭐ Composition root: config → modules → providers |
| 2 | `src/example_hub/main.py` | Lifecycle: `Application.start/stop`, Fleet mounting |
| 3 | `src/example_hub/di/provider.py` | DI wiring: register() binds, boot() initializes Fleet |
| 4 | `src/example_hub/fleet.py` | Fleet: import, start, mount, teardown child demos |
| 5 | `src/example_hub/subsite.py` | SubsiteMiddleware: HTML/JS rewriting for nested mounts |
| 6 | `src/example_hub/controllers/api.py` | JSON API: status endpoint returning fleet snapshot |
| 7 | `src/example_hub/services/registry.py` | Service registry: demo metadata and capabilities |
| 8 | `application.yaml` | Web config (the hub has no demo-specific knobs) |

```
examples/example-hub/
├── src/example_hub/
│   ├── app.py                 # ⭐ composition root (start here)
│   ├── main.py                # entry point / lifecycle
│   ├── fleet.py               # Fleet: mount child demos
│   ├── subsite.py             # HTML/JS rewriting middleware
│   ├── di/
│   │   └── provider.py        # DI wiring + boot() Fleet resolution
│   ├── controllers/api.py     # JSON API: /api/status
│   ├── services/
│   │   └── registry.py        # Service registry + demo metadata
│   └── ui/
│       └── pages.py           # Hub console HTML page
├── application.yaml           # web section (QK_* overrides win)
└── tests/                     # registry + subsite rewrite tests
```

## Tests

```bash
uv run pytest examples/example-hub/tests -q
```
